from unittest.mock import Mock

import pytest

from app.application_layer.contracts.user_repository_protocol import UserRepositoryProtocol
from app.application_layer.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)
from tests.resources.mocks import (
    NONEXISTENT_USER_ID,
    TEST_EMAIL,
    TEST_PASSWORD,
    TEST_USERNAME,
    USER_ID,
    make_user_entity,
    make_user_model_mock,
)


@pytest.fixture
def mock_repo():
    # spec протокола с async-методами → все методы становятся AsyncMock
    return Mock(spec=UserRepositoryProtocol)


@pytest.fixture
def user_service(mock_repo):
    return UserService(repository=mock_repo)


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
    async def test_raises_error_when_email_exists(self, user_service, mock_repo):
        mock_repo.get_user_by_email.return_value = make_user_entity()

        with pytest.raises(UserAlreadyExistsError, match="email"):
            await user_service.register_user(TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD)

    async def test_creates_user_with_hashed_password(self, user_service, mock_repo, user_entity):
        mock_repo.get_user_by_email.return_value = None
        mock_repo.create_user.return_value = user_entity

        result = await user_service.register_user(TEST_USERNAME, TEST_EMAIL, TEST_PASSWORD)

        assert result == user_entity
        mock_repo.create_user.assert_awaited_once()
        call_kwargs = mock_repo.create_user.call_args[1]
        assert call_kwargs["password"] != TEST_PASSWORD


class TestLoginUser:
    async def test_login_success(self, user_service, mock_repo):
        mock_repo.get_user_model_by_email.return_value = make_user_model_mock()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.application_layer.services.user_service.verify_password",
                lambda p, h: True,
            )
            result = await user_service.login_user(TEST_EMAIL, TEST_PASSWORD)

        assert result.id == USER_ID
        assert result.username == TEST_USERNAME

    async def test_login_user_not_found(self, user_service, mock_repo):
        mock_repo.get_user_model_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            await user_service.login_user("nonexistent@example.com", TEST_PASSWORD)

    async def test_login_wrong_password(self, user_service, mock_repo):
        mock_repo.get_user_model_by_email.return_value = make_user_model_mock()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.application_layer.services.user_service.verify_password",
                lambda p, h: False,
            )
            with pytest.raises(InvalidCredentialsError):
                await user_service.login_user(TEST_EMAIL, "wrongpassword")
