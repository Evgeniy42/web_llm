from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Полезная нагрузка валидированного JWT доступа, выпущенного Keycloak."""

    # sub — идентификатор пользователя в Keycloak (UUID)
    sub: str
    email: str | None
    roles: frozenset[str]
