from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.across_layers.entities.token_payload import TokenPayload
from app.across_layers.roles import ROLE_USER, ROLE_VIP_USER
from app.application_layer.contracts.keycloak_protocol import (
    KeycloakClientProtocol,
    KeycloakInvalidCredentialsError,
    KeycloakInvalidTokenError,
    KeycloakUserExistsError,
)
from app.application_layer.contracts.user_repository_protocol import UserRepositoryProtocol
from app.application_layer.services.user_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
    _username_from_email,
)
from tests.resources.mocks import (
    GOOGLE_AUTH_CODE,
    GOOGLE_AUTH_URL,
    GOOGLE_IDP_ALIAS,
    GOOGLE_REDIRECT_URI,
    KEYCLOAK_USER_ID,
    NONEXISTENT_USER_ID,
    REFRESH_TOKEN,
    TEST_EMAIL,
    TEST_PASSWORD,
    TEST_USERNAME,
    USER_ID,
    make_token_info,
    make_user_entity,
)


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
        google_redirect_uri=GOOGLE_REDIRECT_URI,
        google_idp_alias=GOOGLE_IDP_ALIAS,
    )


@pytest.fixture
def user_entity():
    return make_user_entity()


class TestGetUserById:
    async def test_returns_user_when_exists(self, user_service, mock_repo, user_entity):
        mock_repo.get_user_by_id.return_value = user_entity

        result = await user_service.get_user_by_id(USER_ID)

        assert result == user_entity
        mock_repo.get_user_by_id.assert_awaited_once_with(USER_ID)

    async def test_raises_when_not_exists(self, user_service, mock_repo):
        mock_repo.get_user_by_id.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_id(NONEXISTENT_USER_ID)


class TestGetUserByEmail:
    async def test_returns_user_when_exists(self, user_service, mock_repo, user_entity):
        mock_repo.get_user_by_email.return_value = user_entity

        result = await user_service.get_user_by_email(TEST_EMAIL)

        assert result == user_entity
        mock_repo.get_user_by_email.assert_awaited_once_with(TEST_EMAIL)

    async def test_raises_when_not_exists(self, user_service, mock_repo):
        mock_repo.get_user_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_email(TEST_EMAIL)


class TestRegisterUser:
    async def test_raises_error_when_email_exists(self, user_service, mock_repo, mock_keycloak):
        mock_repo.get_user_by_email.return_value = make_user_entity()

        with pytest.raises(UserAlreadyExistsError, match="email"):
            await user_service.register_user(TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD)

        mock_keycloak.create_user.assert_not_awaited()

    async def test_creates_user_in_keycloak_and_locally(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        mock_repo.get_user_by_email.return_value = None
        mock_keycloak.create_user.return_value = KEYCLOAK_USER_ID
        mock_keycloak.authenticate.return_value = make_token_info()
        mock_repo.create_user.return_value = user_entity

        result = await user_service.register_user(TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD)

        assert result.user == user_entity
        assert result.token == make_token_info()
        # Пароль уходит только в Keycloak, локально сохраняется keycloak_id
        mock_keycloak.create_user.assert_awaited_once_with(
            username=TEST_USERNAME,
            email=TEST_EMAIL,
            password=TEST_PASSWORD,
        )
        mock_repo.create_user.assert_awaited_once_with(
            username=TEST_USERNAME,
            email=TEST_EMAIL,
            keycloak_id=KEYCLOAK_USER_ID,
        )
        # Автоматический вход после регистрации
        mock_keycloak.authenticate.assert_awaited_once_with(
            email=TEST_EMAIL,
            password=TEST_PASSWORD,
        )

    async def test_raises_when_keycloak_reports_duplicate(
        self, user_service, mock_repo, mock_keycloak
    ):
        mock_repo.get_user_by_email.return_value = None
        mock_keycloak.create_user.side_effect = KeycloakUserExistsError("duplicate")

        with pytest.raises(UserAlreadyExistsError, match="email"):
            await user_service.register_user(TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD)

        mock_repo.create_user.assert_not_awaited()

    async def test_rolls_back_keycloak_user_when_local_save_fails(
        self, user_service, mock_repo, mock_keycloak
    ):
        mock_repo.get_user_by_email.return_value = None
        mock_keycloak.create_user.return_value = KEYCLOAK_USER_ID
        mock_repo.create_user.side_effect = IntegrityError("stmt", {}, Exception("duplicate"))

        with pytest.raises(UserAlreadyExistsError):
            await user_service.register_user(TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD)

        mock_keycloak.delete_user.assert_awaited_once_with(KEYCLOAK_USER_ID)
        mock_keycloak.authenticate.assert_not_awaited()


class TestLoginUser:
    async def test_login_success(self, user_service, mock_repo, mock_keycloak, user_entity):
        mock_keycloak.authenticate.return_value = make_token_info()
        mock_repo.get_user_by_email.return_value = user_entity

        result = await user_service.login_user(TEST_EMAIL, TEST_PASSWORD)

        assert result.user == user_entity
        assert result.token == make_token_info()
        mock_keycloak.authenticate.assert_awaited_once_with(
            email=TEST_EMAIL,
            password=TEST_PASSWORD,
        )

    async def test_login_invalid_credentials(self, user_service, mock_repo, mock_keycloak):
        mock_keycloak.authenticate.side_effect = KeycloakInvalidCredentialsError("invalid")

        with pytest.raises(InvalidCredentialsError):
            await user_service.login_user(TEST_EMAIL, "wrongpassword")

        mock_repo.get_user_by_email.assert_not_awaited()

    async def test_login_user_missing_locally(self, user_service, mock_repo, mock_keycloak):
        # Keycloak подтвердил пароль, но локального профиля нет
        mock_keycloak.authenticate.return_value = make_token_info()
        mock_repo.get_user_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            await user_service.login_user(TEST_EMAIL, TEST_PASSWORD)


class TestBuildGoogleLoginUrl:
    def test_delegates_to_keycloak_with_google_hint(self, user_service, mock_keycloak):
        mock_keycloak.build_authorization_url.return_value = GOOGLE_AUTH_URL

        url = user_service.build_google_login_url(state="test-state")

        assert url == GOOGLE_AUTH_URL
        mock_keycloak.build_authorization_url.assert_called_once_with(
            redirect_uri=GOOGLE_REDIRECT_URI,
            state="test-state",
            idp_alias=GOOGLE_IDP_ALIAS,
        )


class TestLoginWithGoogle:
    async def test_existing_user_logs_in_without_side_effects(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Пользователь уже регистрировался по паролю: роль user есть в токене,
        # локальный профиль существует — ничего создавать и назначать не нужно
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = TokenPayload(
            sub=KEYCLOAK_USER_ID, email=TEST_EMAIL, roles=frozenset({ROLE_USER})
        )
        mock_repo.get_user_by_email.return_value = user_entity

        result = await user_service.login_with_google(GOOGLE_AUTH_CODE)

        assert result.user == user_entity
        assert result.token == make_token_info()
        mock_keycloak.exchange_code.assert_awaited_once_with(
            code=GOOGLE_AUTH_CODE,
            redirect_uri=GOOGLE_REDIRECT_URI,
        )
        mock_repo.create_user.assert_not_awaited()
        mock_keycloak.assign_role.assert_not_awaited()

    async def test_new_brokered_user_gets_profile_and_default_role(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Пользователь создан брокером Google мимо backend'а: без пароля,
        # без локального профиля и без роли user
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = TokenPayload(
            sub=KEYCLOAK_USER_ID, email=TEST_EMAIL, roles=frozenset()
        )
        mock_repo.get_user_by_email.return_value = None
        mock_repo.create_user.return_value = user_entity

        result = await user_service.login_with_google(GOOGLE_AUTH_CODE)

        assert result.user == user_entity
        mock_repo.create_user.assert_awaited_once_with(
            username=TEST_EMAIL.split("@")[0],
            email=TEST_EMAIL,
            keycloak_id=KEYCLOAK_USER_ID,
        )
        mock_keycloak.assign_role.assert_awaited_once_with(KEYCLOAK_USER_ID, ROLE_USER)

    async def test_new_brokered_user_username_taken_from_google_name(
        self, user_service, mock_repo, mock_keycloak, user_entity
    ):
        # Имя из профиля Google (claim name) имеет приоритет над локальной частью email
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = TokenPayload(
            sub=KEYCLOAK_USER_ID, email=TEST_EMAIL, roles=frozenset(), full_name="Ivan Petrov"
        )
        mock_repo.get_user_by_email.return_value = None
        mock_repo.create_user.return_value = user_entity

        await user_service.login_with_google(GOOGLE_AUTH_CODE)

        mock_repo.create_user.assert_awaited_once_with(
            username="Ivan Petrov",
            email=TEST_EMAIL,
            keycloak_id=KEYCLOAK_USER_ID,
        )

    async def test_raises_when_code_rejected(self, user_service, mock_repo, mock_keycloak):
        mock_keycloak.exchange_code.side_effect = KeycloakInvalidCredentialsError("bad code")

        with pytest.raises(InvalidCredentialsError):
            await user_service.login_with_google(GOOGLE_AUTH_CODE)

        mock_repo.get_user_by_email.assert_not_awaited()

    async def test_raises_when_google_returns_no_email(self, user_service, mock_keycloak):
        mock_keycloak.exchange_code.return_value = make_token_info()
        mock_keycloak.validate_token.return_value = TokenPayload(
            sub=KEYCLOAK_USER_ID, email=None, roles=frozenset()
        )

        with pytest.raises(InvalidCredentialsError, match="email"):
            await user_service.login_with_google(GOOGLE_AUTH_CODE)


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
