"""Тестовые пользователи и конструкторы payload для API-тестов."""

from tests.resources.api import EMAIL_KEY, PASSWORD_KEY, USERNAME_KEY

TEST_USER_1 = {
    USERNAME_KEY: "testuser1",
    EMAIL_KEY: "test1@example.com",
    PASSWORD_KEY: "password123",
}

TEST_USER_2 = {
    USERNAME_KEY: "testuser2",
    EMAIL_KEY: "test2@example.com",
    PASSWORD_KEY: "password456",
}

# Повторяющиеся тестовые значения
NONEXISTENT_USER_ID = 999999
NONEXISTENT_USER_EMAIL = "nonexistent@example.com"
WRONG_PASSWORD = "wrongpassword"
SHORT_PASSWORD = "short"  # меньше минимальных 8 символов из UserRegisterRequestDTO
INVALID_EMAIL = "not-an-email"
# Заглушки идентификаторов Keycloak для тестов репозитория (keycloak_id уникален)
STUB_KEYCLOAK_ID_1 = "00000000-0000-0000-0000-000000000001"
STUB_KEYCLOAK_ID_2 = "00000000-0000-0000-0000-000000000002"


def register_payload(user: dict, **overrides) -> dict:
    """Payload регистрации на основе известного пользователя с переопределениями."""
    return {**user, **overrides}


def login_payload(user: dict, password: str | None = None) -> dict:
    """Payload логина: email из пользователя, пароль — явный или из пользователя."""
    return {
        EMAIL_KEY: user[EMAIL_KEY],
        PASSWORD_KEY: password if password is not None else user[PASSWORD_KEY],
    }
