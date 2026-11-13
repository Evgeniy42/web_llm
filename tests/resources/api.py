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
# Ключ ответа подписки; должен совпадать с полем SubscriptionResponseDTO
MESSAGE_KEY = "message"
# Ключи ответа регистрации/логина; должны совпадать с полями UserAuthResponseDTO
ACCESS_TOKEN_KEY = "access_token"
TOKEN_TYPE_KEY = "token_type"
EXPIRES_IN_KEY = "expires_in"
REFRESH_TOKEN_KEY = "refresh_token"

# Сообщение о запрете чата для пользователя без подписки (роль user)
NO_SUBSCRIPTION_MESSAGE = "У вас нет подписки. Доступ к чату запрещен."

# Ключи query-параметров OAuth callback'а и имя cookie со state
CODE_KEY = "code"
STATE_KEY = "state"
GOOGLE_STATE_COOKIE = "google_oauth_state"

# Пути эндпоинтов (роуты монтируются с префиксом /api, см. app/presentation_layer/controllers)
HEALTH_PATH = "/api/health"
HEALTH_READY_PATH = "/api/health/ready"

REGISTER_PATH = "/api/v1/user/register"
LOGIN_PATH = "/api/v1/user/login"
GOOGLE_LOGIN_PATH = "/api/v1/user/login/google"
GOOGLE_CALLBACK_PATH = "/api/v1/user/login/google/callback"
ME_PATH = "/api/v1/user/me"
LOGOUT_PATH = "/api/v1/user/logout"
SUBSCRIPTION_PATH = "/api/v1/user/subscription"
SEND_MESSAGE_PATH = "/api/v1/chat/send"

# Страница фронтенда, куда callback входа через Google возвращает браузер
# с токенами или ошибкой во fragment (frontend_url по умолчанию в Settings)
FRONTEND_AUTH_CALLBACK_URL = "http://localhost:5173/auth/callback"

USER_BY_ID_PATH_TEMPLATE = "/api/v1/user/{user_id}"


def user_by_id_path(user_id: int) -> str:
    return USER_BY_ID_PATH_TEMPLATE.format(user_id=user_id)


def bearer_headers(access_token: str) -> dict:
    """Заголовки запроса с JWT доступа для защищённых эндпоинтов."""
    return {"Authorization": f"Bearer {access_token}"}
