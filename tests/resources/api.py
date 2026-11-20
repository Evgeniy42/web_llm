"""Глобальные константы API для тестов: пути эндпоинтов и ключи JSON.

Единая точка правды: при изменении роутов (app/presentation_layer/controllers)
или DTO правки вносятся только здесь.
"""

# Ключи JSON-запросов и ответов
ID_KEY = "id"
USERNAME_KEY = "username"
EMAIL_KEY = "email"
DETAIL_KEY = "detail"
STATUS_KEY = "status"
# Ключ ответа чата; должен совпадать с полем ChatResponseDTO
RESPONSE_KEY = "response"
# Ключ ответа подписки; должен совпадать с полем SubscriptionResponseDTO
MESSAGE_KEY = "message"
# Ключ списка ролей в ответе /me; должен совпадать с полем UserResponseDTO
ROLES_KEY = "roles"

# Сообщение о запрете чата для пользователя без подписки (роль user)
NO_SUBSCRIPTION_MESSAGE = "У вас нет подписки. Доступ к чату запрещен."

# Ключи query-параметров OAuth callback'а и имена cookie попытки входа (state + PKCE)
CODE_KEY = "code"
STATE_KEY = "state"
ERROR_KEY = "error"
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_PKCE_VERIFIER_COOKIE = "oauth_code_verifier"

# Имена сессионных cookie, устанавливаемых backend'ом при входе (HttpOnly)
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"

# Пути эндпоинтов (роуты монтируются с префиксом /api, см. app/presentation_layer/controllers)
HEALTH_PATH = "/api/health"
HEALTH_READY_PATH = "/api/health/ready"

LOGIN_PATH = "/api/v1/user/login"
GOOGLE_LOGIN_PATH = "/api/v1/user/login/google"
LOGIN_CALLBACK_PATH = "/api/v1/user/login/callback"
ME_PATH = "/api/v1/user/me"
LOGOUT_PATH = "/api/v1/user/logout"
SUBSCRIPTION_PATH = "/api/v1/user/subscription"
SEND_MESSAGE_PATH = "/api/v1/chat/send"

# Страница фронтенда, куда callback входа возвращает браузер:
# при успехе без параметров (сессия в cookie), при ошибке — с error во fragment
# (frontend_url по умолчанию в Settings)
FRONTEND_AUTH_CALLBACK_URL = "http://localhost:5173/auth/callback"


def bearer_headers(access_token: str) -> dict:
    """Заголовки запроса с JWT доступа для защищённых эндпоинтов."""
    return {"Authorization": f"Bearer {access_token}"}
