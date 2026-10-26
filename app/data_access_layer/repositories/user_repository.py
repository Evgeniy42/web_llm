from advanced_alchemy.exceptions import NotFoundError
from advanced_alchemy.repository import SQLAlchemyAsyncRepository

from app.across_layers.entities.user_entity import UserEntity
from app.application_layer.contracts import UserRepositoryProtocol
from app.data_access_layer.mappers.user_mapper import user_model_to_entity
from app.data_access_layer.models.user_model import UserModel


class UserRepository(
    SQLAlchemyAsyncRepository[UserModel], UserRepositoryProtocol
):
    model_type = UserModel
    count_with_window_function = False

    async def get_user_by_email(self, email: str) -> UserEntity | None:
        model = await self.get_one_or_none(email=email)
        return user_model_to_entity(model) if model else None

    async def get_user_by_id(self, user_id: int) -> UserEntity | None:
        model = await self.get_one_or_none(id=user_id)
        return user_model_to_entity(model) if model else None

    async def create_user(self, username: str, email: str, password: str) -> UserEntity:
        model = UserModel(username=username, email=email, password=password)
        model = await self.add(model)
        return user_model_to_entity(model)

    async def delete_user(self, user_id: int) -> bool:
        try:
            await self.delete(user_id)
        except NotFoundError:
            return False
        return True

    async def update_user(
        self,
        user_id: int,
        username: str | None = None,
        email: str | None = None,
    ) -> UserEntity | None:
        try:
            model = await self.get(user_id)
        except NotFoundError:
            return None
        if username is not None:
            model.username = username
        if email is not None:
            model.email = email
        model = await self.update(model)
        return user_model_to_entity(model)
