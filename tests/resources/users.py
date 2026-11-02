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
INVALID_EMAIL = "not-an-email"
LONG_PASSWORD = "я" * 40  # 80 байт в UTF-8, больше лимита bcrypt (72 байта)
STUB_HASHED_PASSWORD = "hashed_password"  # заглушка хеша для тестов репозитория


def register_payload(user: dict, **overrides) -> dict:
    """Payload регистрации на основе известного пользователя с переопределениями."""
    return {**user, **overrides}


def login_payload(user: dict, password: str | None = None) -> dict:
    """Payload логина: email из пользователя, пароль — явный или из пользователя."""
    return {
        EMAIL_KEY: user[EMAIL_KEY],
        PASSWORD_KEY: password if password is not None else user[PASSWORD_KEY],
    }
