from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.data_access_layer.models.base import BaseORMModel


class UserModel(BaseORMModel):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
