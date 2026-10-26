from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

UsernameStr = Annotated[str, StringConstraints(min_length=3, max_length=50, strip_whitespace=True)]
PasswordStr = Annotated[str, StringConstraints(min_length=8)]


class UserRegisterRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: UsernameStr
    email: EmailStr
    password: PasswordStr


class UserLoginRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class UserResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
