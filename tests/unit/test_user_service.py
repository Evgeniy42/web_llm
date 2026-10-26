from unittest.mock import Mock

import pytest

from app.across_layers.entities.user_entity import UserEntity
from app.application_layer.contracts.user_repository_protocol import UserRepositoryProtocol
from app.application_layer.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserService,
)


@pytest.fixture
def mock_repo():
    return Mock(spec=UserRepositoryProtocol)


@pytest.fixture
def user_service(mock_repo):
    return UserService(repository=mock_repo)


@pytest.fixture
def user_entity():
    return UserEntity(id=1, username="testuser", email="test@example.com")


class TestGetUserById:
    def test_returns_user_when_exists(self, user_service, mock_repo, user_entity):
        mock_repo.get_user_by_id.return_value = user_entity

        result = user_service.get_user_by_id(1)

        assert result == user_entity
        mock_repo.get_user_by_id.assert_called_once_with(1)

    def test_returns_none_when_not_exists(self, user_service, mock_repo):
        mock_repo.get_user_by_id.return_value = None

        result = user_service.get_user_by_id(999)

        assert result is None


class TestRegisterUser:
    def test_raises_error_when_email_exists(self, user_service, mock_repo):
        mock_repo.get_user_by_email.return_value = Mock()

        with pytest.raises(UserAlreadyExistsError, match="email"):
            user_service.register_user("new", "existing@example.com", "password123")

    def test_creates_user_with_hashed_password(self, user_service, mock_repo, user_entity):
        mock_repo.get_user_by_email.return_value = None
        mock_repo.create_user.return_value = user_entity

        result = user_service.register_user("testuser", "test@example.com", "password123")

        assert result == user_entity
        mock_repo.create_user.assert_called_once()
        call_kwargs = mock_repo.create_user.call_args[1]
        assert call_kwargs["password"] != "password123"


class TestLoginUser:
    def test_login_success(self, user_service, mock_repo):
        from app.data_access_layer.models.user_model import UserModel
        mock_model = Mock(spec=UserModel)
        mock_model.id = 1
        mock_model.username = "testuser"
        mock_model.email = "test@example.com"
        mock_model.password = "$2b$12$hashedpassword"
        mock_repo.get_user_model_by_email.return_value = mock_model

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.application_layer.services.user_service.verify_password",
                lambda p, h: True,
            )
            result = user_service.login_user("test@example.com", "password123")

        assert result.id == 1
        assert result.username == "testuser"

    def test_login_user_not_found(self, user_service, mock_repo):
        mock_repo.get_user_model_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            user_service.login_user("nonexistent@example.com", "password123")

    def test_login_wrong_password(self, user_service, mock_repo):
        mock_model = Mock()
        mock_model.password = "$2b$12$hashedpassword"
        mock_repo.get_user_model_by_email.return_value = mock_model

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.application_layer.services.user_service.verify_password",
                lambda p, h: False,
            )
            with pytest.raises(InvalidCredentialsError):
                user_service.login_user("test@example.com", "wrongpassword")
