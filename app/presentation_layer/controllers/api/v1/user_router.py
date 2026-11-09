from dishka.integrations.fastapi import FromDishka, DishkaRoute
from fastapi import APIRouter, HTTPException, status

from app.application_layer.services.user_service import (
    AuthResult,
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)
from app.presentation_layer.dto.user_dto import (
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
