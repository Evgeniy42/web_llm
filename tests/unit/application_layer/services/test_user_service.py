from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.across_layers.entities.token_payload import TokenPayload
from app.across_layers.roles import ROLE_USER, ROLE_VIP_USER
from app.application_layer.contracts.client_contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakError,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
)
from app.application_layer.contracts.service_contracts.user_repository_protocol import UserRepositoryProtocol
from app.application_layer.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
    UserService,
    _username_from_email,
)
from tests.resources.mocks import (
    AUTH_CODE_PREFIX,
    GOOGLE_IDP_ALIAS,
    KEYCLOAK_AUTH_URL,
    KEYCLOAK_USER_ID,
    REDIRECT_URI,
    REFRESH_TOKEN,
    TEST_EMAIL,
    make_token_info,
    make_user_entity,
)

AUTH_CODE = f"{AUTH_CODE_PREFIX}-unit"
CODE_VERIFIER = "unit-test-code-verifier"
CODE_CHALLENGE = "unit-test-code-challenge"


@pytest.fixture
def mock_repo():
    # spec протокола с async-методами → все методы становятся AsyncMock
    return Mock(spec=UserRepositoryProtocol)


@pytest.fixture
def mock_keycloak():
    return Mock(spec=KeycloakClientProtocol)


@pytest.fixture
def user_service(mock_repo, mock_keycloak):
    return UserService(
        repository=mock_repo,
        keycloak=mock_keycloak,
        redirect_uri=REDIRECT_URI,
        google_idp_alias=GOOGLE_IDP_ALIAS,
    )


@pytest.fixture
def user_entity():
    return make_user_entity()


def _token_payload(
    sub: str = KEYCLOAK_USER_ID,
    email: str | None = TEST_EMAIL,
    roles: frozenset[str] = frozenset({ROLE_USER}),
    full_name: str | None = None,
) -> TokenPayload:
    return TokenPayload(sub=sub, email=email, roles=roles, full_name=full_name)


class TestGetUserByKeycloakId:
    async def test_returns_user_when_exists(self, user_service, mock_repo, user_entity):
        mock_repo.get_user_by_keycloak_id.return_value = user_entity

        result = await user_service.get_user_by_keycloak_id(KEYCLOAK_USER_ID)

        assert result == user_entity
        mock_repo.get_user_by_keycloak_id.assert_awaited_once_with(KEYCLOAK_USER_ID)

    async def test_raises_when_not_exists(self, user_service, mock_repo):
        mock_repo.get_user_by_keycloak_id.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_keycloak_id(KEYCLOAK_USER_ID)


class TestBuildLoginUrl:
    def test_delegates_to_keycloak_with_pkce(self, user_service, mock_keycloak):
        mock_keycloak.build_authorization_url.return_value = KEYCLOAK_AUTH_URL

        url = user_service.build_login_url(state="test-state", code_challenge=CODE_CHALLENGE)

        assert url == KEYCLOAK_AUTH_URL
        mock_keycloak.build_authorization_url.assert_called_once_with(
            redirect_uri=REDIRECT_URI,
            state="test-state",
            code_challenge=CODE_CHALLENGE,
            idp_alias=None,
        )

    def test_delegates_with_google_hint(self, user_service, mock_keycloak):
        mock_keycloak.build_authorization_url.return_value = KEYCLOAK_AUTH_URL

        user_service.build_login_url(
            state="test-state", code_challenge=CODE_CHALLENGE, idp_alias=GOOGLE_IDP_ALIAS
        )

        mock_keycloak.build_authorization_url.assert_called_once_with(
            redirect_uri=REDIRECT_URI,
            state="test-state",
            code_challenge=CODE_CHALLENGE,
            idp_alias=GOOGLE_IDP_ALIAS,
        )


class TestCompleteLogin:
    async def test_existing_user_logs_in_without_side_effects(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Профиль уже есть (поиск по sub, не по email), роль user в токене —
        # ничего создавать и назначать не нужно
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload()
        mock_repo.get_user_by_keycloak_id.return_value = user_entity

        result = await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        assert result.user == user_entity
        assert result.token == make_token_info()
        mock_keycloak.exchange_code.assert_awaited_once_with(
            code=AUTH_CODE,
            redirect_uri=REDIRECT_URI,
            code_verifier=CODE_VERIFIER,
        )
        mock_repo.get_user_by_keycloak_id.assert_awaited_once_with(KEYCLOAK_USER_ID)
        mock_repo.create_user.assert_not_awaited()
        mock_keycloak.assign_role.assert_not_awaited()

    async def test_new_user_gets_profile(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Пользователь создан Keycloak мимо backend'а: локального профиля нет
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload()
        mock_repo.get_user_by_keycloak_id.return_value = None
        mock_repo.create_user.return_value = user_entity

        result = await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        assert result.user == user_entity
        # Имени из соцсети нет — имя выводится из локальной части email
        mock_repo.create_user.assert_awaited_once_with(
            username=TEST_EMAIL.split("@")[0],
            email=TEST_EMAIL,
            keycloak_id=KEYCLOAK_USER_ID,
        )

    async def test_new_user_username_taken_from_google_name(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Имя из профиля Google (claim name) имеет приоритет над локальной частью email
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload(full_name="Ivan Petrov")
        mock_repo.get_user_by_keycloak_id.return_value = None
        mock_repo.create_user.return_value = user_entity

        await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        mock_repo.create_user.assert_awaited_once_with(
            username="Ivan Petrov",
            email=TEST_EMAIL,
            keycloak_id=KEYCLOAK_USER_ID,
        )

    async def test_profile_creation_is_idempotent_on_race(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Гонка параллельных первых входов: create упёрся в unique keycloak_id,
        # повторное чтение возвращает уже созданный профиль — вход продолжается
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload()
        mock_repo.get_user_by_keycloak_id.side_effect = [None, user_entity]
        mock_repo.create_user.side_effect = IntegrityError("stmt", {}, Exception("duplicate"))

        result = await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        assert result.user == user_entity
        assert mock_repo.get_user_by_keycloak_id.await_count == 2

    async def test_assigns_default_role_when_missing(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Роли user в токене нет: backend доназначает её в Keycloak
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload(roles=frozenset())
        mock_repo.get_user_by_keycloak_id.return_value = user_entity

        await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        mock_keycloak.assign_role.assert_awaited_once_with(KEYCLOAK_USER_ID, ROLE_USER)

    async def test_role_assignment_failure_does_not_fail_login(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Сбой назначения роли не должен ронять вход: роль назначится при следующем логине
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload(roles=frozenset())
        mock_keycloak.assign_role.side_effect = KeycloakError("Keycloak недоступен")
        mock_repo.get_user_by_keycloak_id.return_value = user_entity

        result = await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        assert result.user == user_entity

    async def test_raises_when_code_rejected(self, user_service, mock_repo, mock_keycloak):
        mock_keycloak.exchange_code.side_effect = KeycloakInvalidCredentialsError("bad code")

        with pytest.raises(InvalidCredentialsError):
            await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)

        mock_repo.get_user_by_keycloak_id.assert_not_awaited()

    async def test_raises_when_keycloak_returns_no_email(self, user_service, mock_keycloak):
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = _token_payload(email=None)

        with pytest.raises(InvalidCredentialsError, match="email"):
            await user_service.complete_login(AUTH_CODE, CODE_VERIFIER)


class TestUsernameFromEmail:
    @pytest.mark.parametrize(
        ("email", "expected"),
        [
            ("testuser@example.com", "testuser"),
            # Локальная часть короче минимума имени — дополняется префиксом
            ("ab@example.com", "user_ab"),
            # Имя обрезается под VARCHAR(50) из UserModel
            ("a" * 100 + "@example.com", "a" * 50),
        ],
    )
    def test_derives_username(self, email, expected):
        assert _username_from_email(email) == expected


class TestGrantSubscription:
    async def test_assigns_vip_role_in_keycloak(self, user_service, mock_keycloak):
        await user_service.grant_subscription(KEYCLOAK_USER_ID)

        mock_keycloak.assign_role.assert_awaited_once_with(KEYCLOAK_USER_ID, ROLE_VIP_USER)


class TestLogoutUser:
    async def test_logout_revokes_refresh_token(self, user_service, mock_keycloak):
        await user_service.logout_user(REFRESH_TOKEN)

        mock_keycloak.logout.assert_awaited_once_with(refresh_token=REFRESH_TOKEN)

    async def test_logout_invalid_token(self, user_service, mock_keycloak):
        mock_keycloak.logout.side_effect = KeycloakInvalidTokenError("invalid")

        with pytest.raises(InvalidTokenError):
            await user_service.logout_user(REFRESH_TOKEN)
