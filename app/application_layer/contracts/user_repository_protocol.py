from typing import Protocol

from app.across_layers.entities.user_entity import UserEntity


class UserRepositoryProtocol(Protocol):
    async def get_user_by_id(self, user_id: int) -> UserEntity | None: ...

    async def get_user_by_email(self, email: str) -> UserEntity | None: ...

    async def create_user(self, username: str, email: str, keycloak_id: str) -> UserEntity: ...

    async def delete_user(self, user_id: int) -> bool: ...

    async def update_user(
        self,
        user_id: int,
        username: str | None = None,
        email: str | None = None,
    ) -> UserEntity | None: ...
