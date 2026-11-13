import secrets
from urllib.parse import urlencode

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.application_layer.services.user_service import (
    AuthResult,
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)
from app.configuration.settings import Settings
from app.presentation_layer.dependencies.auth import CurrentUser
from app.presentation_layer.dto.user_dto import (
    SubscriptionResponseDTO,
    UserAuthResponseDTO,
    UserLoginRequestDTO,
    UserLogoutRequestDTO,
    UserRegisterRequestDTO,
    UserResponseDTO,
)

router = APIRouter(
    tags=["user"],
    route_class=DishkaRoute
)

# Защита OAuth callback'а от CSRF: state хранится в cookie и сверяется
# с query-параметром, который Keycloak возвращает после входа через Google
GOOGLE_OAUTH_STATE_COOKIE = "google_oauth_state"
GOOGLE_OAUTH_STATE_TTL_SECONDS = 600


def _to_auth_response(result: AuthResult) -> UserAuthResponseDTO:
    return UserAuthResponseDTO(
        id=result.user.id,
        username=result.user.username,
        email=result.user.email,
        access_token=result.token.access_token,
        token_type=result.token.token_type,
        expires_in=result.token.expires_in,
        refresh_token=result.token.refresh_token,
    )


def _frontend_redirect(frontend_url: str, params: dict[str, str]) -> RedirectResponse:
    """Редирект браузера на страницу входа фронтенда с параметрами во fragment.

    Токены передаются во fragment, а не в query: fragment не попадает
    в access-логи прокси и не уходит на сервер фронтенда.
    """
    url = f"{frontend_url}/auth/callback#{urlencode(params)}"
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.post("/register", response_model=UserAuthResponseDTO, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequestDTO,
    service: FromDishka[UserService],
):
    """Регистрирует нового пользователя и сразу аутентифицирует его.

    Args:
        request: данные регистрации — имя, email и пароль.

    Returns:
        Данные созданного пользователя и JWT-токены сессии. При занятом email — 409 Conflict.
    """
    try:
        result = await service.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
        )

        return _to_auth_response(result)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post("/login", response_model=UserAuthResponseDTO)
async def login(
    request: UserLoginRequestDTO,
    service: FromDishka[UserService],
):
    """Выполняет вход пользователя по email и паролю.

    Учётные данные проверяются в Keycloak; при успехе клиент получает JWT,
    который использует для запросов в рамках сессии.

    Args:
        request: учётные данные — email и пароль.

    Returns:
        Данные пользователя и JWT-токены сессии. При неверной паре email/пароль — 401 Unauthorized.
    """
    try:
        result = await service.login_user(
            email=request.email,
            password=request.password,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    return _to_auth_response(result)


@router.get("/login/google")
async def login_google(
    service: FromDishka[UserService],
) -> RedirectResponse:
    """Перенаправляет браузер на страницу входа Google через Keycloak.

    Это точка входа для кнопки «Войти через Google» на клиенте: обычная ссылка,
    JS-код не нужен. State защиты от CSRF сохраняется в cookie и проверяется
    в callback'е.

    Returns:
        302 Redirect на URL авторизации Keycloak с kc_idp_hint=google.
    """
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(
        url=service.build_google_login_url(state),
        status_code=status.HTTP_302_FOUND,
    )
    # httponly: cookie нужен только backend'у в callback; samesite=lax пропускает
    # cookie при возврате браузера с Google (top-level GET-навигация)
    response.set_cookie(
        GOOGLE_OAUTH_STATE_COOKIE,
        value=state,
        max_age=GOOGLE_OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/login/google/callback")
async def login_google_callback(
    request: Request,
    service: FromDishka[UserService],
    settings: FromDishka[Settings],
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    """Принимает браузер от Keycloak после входа через Google и возвращает его на фронтенд.

    Keycloak возвращает браузер сюда с кодом авторизации; backend обменивает
    его на токены и редиректит браузер на фронтенд, передавая токены сессии
    во fragment. Ошибки входа не отдаются JSON'ом: браузер здесь в навигации,
    поэтому при любой ошибке он тоже уходит на фронтенд с error во fragment.

    Args:
        code: одноразовый код авторизации от Keycloak.
        state: значение state, сверяемое с cookie (защита от CSRF).

    Returns:
        302 Redirect на {frontend_url}/auth/callback: при успехе во fragment
        access_token, refresh_token, token_type и expires_in; при ошибке — error.
    """
    expected_state = request.cookies.get(GOOGLE_OAUTH_STATE_COOKIE)
    redirect: RedirectResponse
    if (
        not code
        or not state
        or not expected_state
        or not secrets.compare_digest(state, expected_state)
    ):
        redirect = _frontend_redirect(
            settings.frontend_url,
            {"error": "Некорректный ответ авторизации Google: отсутствует или не совпадает state"},
        )
    else:
        try:
            result = await service.login_with_google(code)
        except InvalidCredentialsError as e:
            redirect = _frontend_redirect(settings.frontend_url, {"error": str(e)})
        else:
            params = {
                "access_token": result.token.access_token,
                "token_type": result.token.token_type,
                "expires_in": str(result.token.expires_in),
            }
            if result.token.refresh_token is not None:
                params["refresh_token"] = result.token.refresh_token
            redirect = _frontend_redirect(settings.frontend_url, params)

    # State одноразовый: cookie больше не нужен ни при успехе, ни при ошибке
    redirect.delete_cookie(GOOGLE_OAUTH_STATE_COOKIE)
    return redirect


@router.post("/subscription", response_model=SubscriptionResponseDTO)
async def subscribe(
    user: CurrentUser,
    service: FromDishka[UserService],
):
    """Оформляет подписку текущему пользователю (имитация оплаты).

    Назначает пользователю realm-роль vip_user в Keycloak. Пользователь
    определяется по sub из JWT в заголовке Authorization. Новая роль
    появится в токене только после повторного входа.

    Args:
        user: полезная нагрузка валидированного JWT текущего пользователя.

    Returns:
        Подтверждение оформления подписки. Без валидного токена — 401 Unauthorized.
    """
    await service.grant_subscription(keycloak_id=user.sub)
    return SubscriptionResponseDTO(
        message="Подписка оформлена. Перевойдите, чтобы получить токен с доступом к чату."
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: UserLogoutRequestDTO,
    service: FromDishka[UserService],
):
    """Завершает сессию пользователя: отзывает refresh-токен в Keycloak.

    Access-токен остаётся валидным до истечения его expires_in —
    это ограничение stateless JWT.

    Args:
        request: refresh-токен сессии, полученный при входе или регистрации.

    Returns:
        Пустой ответ 204. Если токен недействителен — 401 Unauthorized.
    """
    try:
        await service.logout_user(refresh_token=request.refresh_token)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e


# /me объявлен раньше /{user_id}: иначе "me" попадёт в int-валидацию параметра пути
@router.get("/me", response_model=UserResponseDTO)
async def get_me(
    user: CurrentUser,
    service: FromDishka[UserService],
):
    """Возвращает профиль текущего пользователя по Bearer JWT.

    Пользователь определяется по email из полезной нагрузки токена.

    Args:
        user: полезная нагрузка валидированного JWT текущего пользователя.

    Returns:
        Данные пользователя. Без валидного токена, без email в токене
        или при отсутствии локального профиля — 401 Unauthorized.
    """
    if user.email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не содержит email пользователя",
        )
    try:
        profile = await service.get_user_by_email(user.email)
    except UserNotFoundError as e:
        # Токен валиден, но локального профиля нет — для клиента это невалидная сессия
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    return UserResponseDTO.model_validate(profile)


@router.get("/{user_id}", response_model=UserResponseDTO)
async def get_user_by_id(
    user_id: int,
    service: FromDishka[UserService],
):
    """Возвращает пользователя по идентификатору.

    Args:
        user_id: идентификатор пользователя.

    Returns:
        Данные пользователя. Если пользователь не найден — 404 Not Found.
    """
    try:
        user = await service.get_user_by_id(user_id)

        return UserResponseDTO.model_validate(user)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
