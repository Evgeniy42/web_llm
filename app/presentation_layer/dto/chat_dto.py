from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

MessageStr = Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ChatRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: MessageStr


class ChatResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    response: str
