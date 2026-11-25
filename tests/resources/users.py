"""Тестовые пользователи для API-тестов.

Паролей нет: ввод логина/пароля и регистрация идут на странице Keycloak,
в тестах её заменяет MockKeycloakClient.
"""

from tests.resources.api import EMAIL_KEY, USERNAME_KEY

TEST_USER_1 = {
    USERNAME_KEY: "testuser1",
    EMAIL_KEY: "test1@example.com",
}

TEST_USER_2 = {
    USERNAME_KEY: "testuser2",
    EMAIL_KEY: "test2@example.com",
}

# Заглушки идентификаторов Keycloak для тестов репозитория (keycloak_id уникален)
STUB_KEYCLOAK_ID_1 = "00000000-0000-0000-0000-000000000001"
STUB_KEYCLOAK_ID_2 = "00000000-0000-0000-0000-000000000002"
