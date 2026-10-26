from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class UserEntity:
    id: int
    username: str = field(compare=False)
    email: str = field(compare=False)
