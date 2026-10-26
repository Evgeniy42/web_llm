from dataclasses import dataclass

from app.across_layers.entities.user_entity import UserEntity
from app.application_layer.contracts.user_repository_protocol import UserRepositoryProtocol
from app.application_layer.utils.hashed_password import hash_password, verify_password


class UserNotFoundError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


@dataclass(slots=True)
class UserService:
    repository: UserRepositoryProtocol

    def get_user_by_id(self, user_id: int) -> UserEntity | None:
        return self.repository.get_user_by_id(user_id)

    def register_user(self, username: str, email: str, password: str) -> UserEntity:
        if self.repository.get_user_by_email(email):
            raise UserAlreadyExistsError("Пользователь с таким email уже существует!")

        hashed = hash_password(password)
        return self.repository.create_user(
            username=username,
            email=email,
            password=hashed,
        )

    def login_user(self, email: str, password: str) -> UserEntity:
        user_with_password = self.repository.get_user_model_by_email(email)
        if not user_with_password:
            raise InvalidCredentialsError("Неправильный пароль или логин!")

        if not verify_password(password, user_with_password.password):
            raise InvalidCredentialsError("Неправильный пароль или логин!")

        return UserEntity(
            id=user_with_password.id,
            username=user_with_password.username,
            email=user_with_password.email,
        )
