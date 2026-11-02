"""Моковые значения и фабрики для unit-тестов application_layer."""

from unittest.mock import Mock

from app.across_layers.entities.user_entity import UserEntity
from app.data_access_layer.models.user_model import UserModel

# Повторяющиеся тестовые значения
USER_ID = 1
NONEXISTENT_USER_ID = 999
TEST_USERNAME = "testuser"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"
HASHED_PASSWORD = "$2b$12$hashedpassword"

# Значения для ChatService
USER_MESSAGE = "Hello"
LLM_RESPONSE = "Привет!"


def make_user_entity() -> UserEntity:
    return UserEntity(id=USER_ID, username=TEST_USERNAME, email=TEST_EMAIL)


def make_user_model_mock() -> Mock:
    """Мок ORM-модели пользователя с паролем (для сценариев логина)."""
    mock_model = Mock(spec=UserModel)
    mock_model.id = USER_ID
    mock_model.username = TEST_USERNAME
    mock_model.email = TEST_EMAIL
    mock_model.password = HASHED_PASSWORD
    return mock_model
