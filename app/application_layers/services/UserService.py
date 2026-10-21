from sqlalchemy.orm import Session

from app.data_access_layer.models import User
from app.data_access_layer.repositories import UserRepository

from app.application_layers.utils.hashed_password import hash_password, verify_password

class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repository = UserRepository(db)

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.user_repository.get_user_by_id(user_id)

    def register_user(self, username: str, email: str, password: str) -> tuple[User | None, str | None]:
        existing_user = self.user_repository.get_user_by_email(email)

        if existing_user:
            return None, "Пользователь с таким email уже существует!"

        hashed_password = hash_password(password)
        user = self.user_repository.create_user(
            username=username,
            email=email,
            password=hashed_password
        )
        return user, None

    def login_user(self, email: str, password: str) -> tuple[User | None, str | None]:
        user = self.user_repository.get_user_by_email(email)

        if not user or not verify_password(password, user.password):
            return None, "Неправильный пароль или логин!"

        return user, None
            
        

