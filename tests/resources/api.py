"""Глобальные константы API для тестов: пути эндпоинтов и ключи JSON.

Единая точка правды: при изменении роутов (app/presentation_layer/controllers)
или DTO правки вносятся только здесь.
"""

# Ключи JSON-запросов и ответов
ID_KEY = "id"
USERNAME_KEY = "username"
EMAIL_KEY = "email"
PASSWORD_KEY = "password"
DETAIL_KEY = "detail"
STATUS_KEY = "status"
# Ключ ответа чата; должен совпадать с полем ChatResponseDTO
RESPONSE_KEY = "response"
# Ключи ответа регистрации/логина; должны совпадать с полями UserAuthResponseDTO
ACCESS_TOKEN_KEY = "access_token"
TOKEN_TYPE_KEY = "token_type"
EXPIRES_IN_KEY = "expires_in"
REFRESH_TOKEN_KEY = "refresh_token"

# Пути эндпоинтов (роуты монтируются с префиксом /api, см. app/presentation_layer/controllers)
HEALTH_PATH = "/api/health"
HEALTH_READY_PATH = "/api/health/ready"

REGISTER_PATH = "/api/v1/user/register"
LOGIN_PATH = "/api/v1/user/login"
LOGOUT_PATH = "/api/v1/user/logout"
SEND_MESSAGE_PATH = "/api/v1/chat/send"

USER_BY_ID_PATH_TEMPLATE = "/api/v1/user/{user_id}"


def user_by_id_path(user_id: int) -> str:
    return USER_BY_ID_PATH_TEMPLATE.format(user_id=user_id)
