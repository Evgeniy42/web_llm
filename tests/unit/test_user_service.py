from unittest.mock import Mock

import pytest

from app.application_layers.services.UserService import UserService


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_repo():
    repo = Mock()
    return repo


@pytest.fixture
def user_service(mock_db, mock_repo):
    service = UserService(mock_db)
    service.user_repository = mock_repo
    return service


class TestGetUserById:
    def test_returns_user_when_exists(self, user_service, mock_repo):
        # Arrange
        mock_user = Mock(id=1, username="test", email="test@example.com")
        mock_repo.get_user_by_id.return_value = mock_user

        # Act
        result = user_service.get_user_by_id(1)

        # Assert
        assert result == mock_user
        mock_repo.get_user_by_id.assert_called_once_with(1)

    def test_returns_none_when_not_exists(self, user_service, mock_repo):
        # Arrange
        mock_repo.get_user_by_id.return_value = None

        # Act
        result = user_service.get_user_by_id(999)

        # Assert
        assert result is None


class TestRegisterUser:
    def test_returns_error_when_email_exists(self, user_service, mock_repo):
        # Arrange
        mock_repo.get_user_by_email.return_value = Mock()

        # Act
        user, error = user_service.register_user(
            username="new",
            email="existing@example.com",
            password="password123"
        )

        # Assert
        assert user is None
        assert error == "Пользователь с таким email уже существует!"

    def test_creates_user_with_hashed_password(self, user_service, mock_repo):
        # Arrange
        mock_repo.get_user_by_email.return_value = None
        mock_repo.create_user.return_value = Mock(id=1, username="new")

        # Act
        user, error = user_service.register_user(
            username="new",
            email="new@example.com",
            password="password123"
        )

        # Assert
        assert error is None
        assert user is not None
        mock_repo.create_user.assert_called_once()
        call_kwargs = mock_repo.create_user.call_args[1]
        assert call_kwargs["password"] != "password123"  # пароль захеширован
