from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MessageStr = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ChatRequestDTO(BaseModel):
    """Сообщение пользователя для отправки в чат."""

    model_config = ConfigDict(extra="forbid")

    message: MessageStr = Field(description="Текст сообщения, 1-2000 символов")


class ChatResponseDTO(BaseModel):
    """Ответ чата на сообщение пользователя."""

    model_config = ConfigDict(from_attributes=True)

    response: str = Field(description="Сгенерированный текст ответа")
