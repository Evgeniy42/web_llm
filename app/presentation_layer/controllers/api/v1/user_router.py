from dishka.integrations.fastapi import FromDishka, DishkaRoute
from fastapi import APIRouter, HTTPException, status

from app.application_layer.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)
from app.presentation_layer.dto.user_dto import (
    UserLoginRequestDTO,
    UserRegisterRequestDTO,
    UserResponseDTO,
)

router = APIRouter(
    tags=["user"],
    route_class=DishkaRoute
)


@router.post("/register", response_model=UserResponseDTO, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequestDTO,
    service: FromDishka[UserService],
):
    """Регистрирует нового пользователя.

    Args:
        request: данные регистрации — имя, email и пароль.

    Returns:
        Данные созданного пользователя. При занятом email — 409 Conflict.
    """
    try:
        user = await service.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
        )

        return UserResponseDTO.model_validate(user)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post("/login", response_model=UserResponseDTO)
async def login(
    request: UserLoginRequestDTO,
    service: FromDishka[UserService],
):
    """Выполняет вход пользователя по email и паролю.

    Args:
        request: учётные данные — email и пароль.

    Returns:
        Данные пользователя. При неверной паре email/пароль — 401 Unauthorized.
    """
    try:
        user = await service.login_user(
            email=request.email,
            password=request.password,
        )

        return UserResponseDTO.model_validate(user)
    except InvalidCredentialsError as e:
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
