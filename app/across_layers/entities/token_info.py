from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenInfo:
    """Токены сессии, выпущенные Keycloak после успешной аутентификации."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
