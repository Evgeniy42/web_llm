from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.across_layers.roles import ROLE_VIP_USER
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
)
from tests.resources.mocks import (
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
    return UserService(repository=mock_repo, keycloak=mock_keycloak)


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
