from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.configuration.database import get_db
from app.application_layers.services.UserService import UserService
from app.presentation_layer.dto.UserDto import (
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@router.post("/register", response_model=UserResponse)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    user, error = UserService(db).register_user(
        username=request.username,
        email=request.email,
        password=request.password,
    )
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )
    return user


@router.post("/login", response_model=UserResponse)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    user, error = UserService(db).login_user(
        email=request.email,
        password=request.password,
    )
    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
        )

    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = UserService(db).get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    return user