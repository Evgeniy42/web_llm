from app.across_layers.entities.user_entity import UserEntity
from app.data_access_layer.models.user_model import UserModel


def user_model_to_entity(model: UserModel) -> UserEntity:
    return UserEntity(
        id=model.id,
        username=model.username,
        email=model.email,
    )
