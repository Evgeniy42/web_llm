import base64
import contextlib
import hashlib
import secrets
from urllib.parse import urlencode

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.application_layer.services.user_service import (
    AuthResult,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
    UserService,
)
from app.configuration.settings import Settings
from app.presentation_layer.dependencies.auth import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    CurrentUser,
)
from app.presentation_layer.dto.user_dto import (
    SubscriptionResponseDTO,
    UserResponseDTO,
)

router = APIRouter(
    tags=["user"],
    route_class=DishkaRoute
)

# Защита OAuth callback'а от CSRF и подмены кода: state и PKCE-verifier
# хранятся в HttpOnly-cookie и сверяются с ответом Keycloak в callback'е
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_PKCE_VERIFIER_COOKIE = "oauth_code_verifier"
OAUTH_FLOW_COOKIE_TTL_SECONDS = 600

# Время жизни refresh-cookie: с запасом под SSO-сессию realm'а (30 дней)
REFRESH_TOKEN_COOKIE_TTL_SECONDS = 60 * 60 * 24 * 30


def _generate_pkce_pair() -> tuple[str, str]:
    """Генерирует PKCE-пару (verifier, challenge) для метода S256 (RFC 7636)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _start_login(service: UserService, idp_alias: str | None = None) -> RedirectResponse:
    """Начинает попытку входа: state + PKCE в HttpOnly-cookie, 302 на Keycloak."""
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce_pair()
    response = RedirectResponse(
        url=service.build_login_url(state=state, code_challenge=code_challenge, idp_alias=idp_alias),
        status_code=status.HTTP_302_FOUND,
    )
    # httponly: cookie нужны только backend'у в callback; samesite=lax пропускает
    # их при возврате браузера с Keycloak (top-level GET-навигация)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        value=state,
        max_age=OAUTH_FLOW_COOKIE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        OAUTH_PKCE_VERIFIER_COOKIE,
        value=code_verifier,
        max_age=OAUTH_FLOW_COOKIE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


def _frontend_error_redirect(frontend_url: str, error: str) -> RedirectResponse:
    """Редирект браузера на страницу фронтенда с сообщением об ошибке во fragment.

    Fragment, а не query: сообщение не попадает в access-логи прокси
    и не уходит на сервер фронтенда.
    """
    url = f"{frontend_url}/auth/callback#{urlencode({'error': error})}"
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


def _set_session_cookies(response: Response, result: AuthResult) -> None:
    """Устанавливает сессионные cookie с токенами Keycloak.

    Токены недоступны JS фронтенда (HttpOnly) и не передаются в URL.
    Secure не выставлен: локальная разработка идёт по HTTP; для продакшена
    (HTTPS) включить secure=True.
    """
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        value=result.token.access_token,
        max_age=result.token.expires_in,
        httponly=True,
        samesite="lax",
        path="/",
    )
    if result.token.refresh_token is not None:
        response.set_cookie(
            REFRESH_TOKEN_COOKIE,
            value=result.token.refresh_token,
            max_age=REFRESH_TOKEN_COOKIE_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            path="/",
        )


def _clear_oauth_flow_cookies(response: Response) -> None:
    """Сбрасывает cookie попытки входа: state и PKCE-verifier одноразовые."""
    response.delete_cookie(OAUTH_STATE_COOKIE)
    response.delete_cookie(OAUTH_PKCE_VERIFIER_COOKIE)


@router.get("/login")
async def login(
    service: FromDishka[UserService],
) -> RedirectResponse:
    """Перенаправляет браузер на страницу входа Keycloak (логин/пароль и регистрация).

    Это точка входа для кнопки «Войти» на клиенте: обычная ссылка, JS-код не
    нужен. State (CSRF) и PKCE-verifier сохраняются в HttpOnly-cookie и
    проверяются в callback'е.

    Returns:
        302 Redirect на страницу авторизации Keycloak.
    """
    return _start_login(service)


@router.get("/login/google")
async def login_google(
    service: FromDishka[UserService],
) -> RedirectResponse:
    """Перенаправляет браузер на форму входа Google через Keycloak.

    Отличается от /login только kc_idp_hint=google: Keycloak сразу ведёт
    на форму Google, минуя собственную страницу логина.

    Returns:
        302 Redirect на URL авторизации Keycloak с kc_idp_hint=google.
    """
    return _start_login(service, idp_alias=service.google_idp_alias)


@router.get("/login/callback")
async def login_callback(
    request: Request,
    service: FromDishka[UserService],
    settings: FromDishka[Settings],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Принимает браузер от Keycloak после входа и возвращает его на фронтенд.

    Единый callback для входа через форму Keycloak и через Google. Backend
    сверяет state, обменивает код на токены (с PKCE-verifier из cookie),
    валидирует JWT, при первом входе создаёт локальный профиль и устанавливает
    сессионные cookie. Браузер здесь в навигации, поэтому и успех, и ошибка
    завершаются редиректом на фронтенд — без JSON.

    Args:
        code: одноразовый код авторизации от Keycloak.
        state: значение state, сверяемое с cookie (защита от CSRF).
        error: код ошибки, если Keycloak вернул браузер с отказом.

    Returns:
        302 Redirect на {frontend_url}/auth/callback: при успехе без параметров
        (сессия в cookie), при ошибке — с error во fragment.
    """
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    code_verifier = request.cookies.get(OAUTH_PKCE_VERIFIER_COOKIE)

    redirect: RedirectResponse
    if (
        error
        or not code
        or not state
        or not expected_state
        or not code_verifier
        or not secrets.compare_digest(state, expected_state)
    ):
        redirect = _frontend_error_redirect(
            settings.frontend_url,
            "Некорректный ответ авторизации: отсутствует или не совпадает state",
        )
    else:
        try:
            result = await service.complete_login(code, code_verifier)
        except InvalidCredentialsError as e:
            redirect = _frontend_error_redirect(settings.frontend_url, str(e))
        else:
            redirect = RedirectResponse(
                url=f"{settings.frontend_url}/auth/callback",
                status_code=status.HTTP_302_FOUND,
            )
            _set_session_cookies(redirect, result)

    # State и PKCE-verifier одноразовые: cookie больше не нужны ни при успехе, ни при ошибке
    _clear_oauth_flow_cookies(redirect)
    return redirect


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    service: FromDishka[UserService],
) -> Response:
    """Завершает сессию: отзывает refresh-токен в Keycloak и очищает cookie.

    Refresh-токен берётся из сессионной cookie (тело запроса не нужно).
    Access-токен остаётся валидным до истечения его expires_in — это
    ограничение stateless JWT.

    Returns:
        Всегда пустой ответ 204: без cookie или с уже отозванным токеном
        выход считается выполненным (идемпотентность).
    """
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if refresh_token:
        # Сессия в Keycloak уже завершена — для клиента результат тот же
        with contextlib.suppress(InvalidTokenError):
            await service.logout_user(refresh_token=refresh_token)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserResponseDTO)
async def get_me(
    user: CurrentUser,
    service: FromDishka[UserService],
):
    """Возвращает профиль текущего пользователя и его роли из токена сессии.

    Пользователь определяется по sub (keycloak_id) из валидированного JWT —
    не по email: email может меняться и расходиться в регистре с Keycloak.
    Роли нужны фронтенду для UI: токен хранится в HttpOnly-cookie и JS его
    не декодирует.

    Args:
        user: полезная нагрузка валидированного JWT текущего пользователя.

    Returns:
        Данные пользователя и его realm-роли. Без валидной сессии или при
        отсутствии локального профиля — 401 Unauthorized.
    """
    try:
        profile = await service.get_user_by_keycloak_id(user.sub)
    except UserNotFoundError as e:
        # Токен валиден, но локального профиля нет — для клиента это невалидная сессия
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    return UserResponseDTO(
        id=profile.id,
        username=profile.username,
        email=profile.email,
        roles=sorted(user.roles),
    )


@router.post("/subscription", response_model=SubscriptionResponseDTO)
async def subscribe(
    user: CurrentUser,
    service: FromDishka[UserService],
):
    """Оформляет подписку текущему пользователю (имитация оплаты).

    Назначает пользователю realm-роль vip_user в Keycloak. Пользователь
    определяется по sub из JWT сессии. Новая роль появится в токене
    только после повторного входа.

    Args:
        user: полезная нагрузка валидированного JWT текущего пользователя.

    Returns:
        Подтверждение оформления подписки. Без валидной сессии — 401 Unauthorized.
    """
    await service.grant_subscription(keycloak_id=user.sub)
    return SubscriptionResponseDTO(
        message="Подписка оформлена. Перевойдите, чтобы получить токен с доступом к чату."
    )
