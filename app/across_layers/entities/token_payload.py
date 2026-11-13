from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Полезная нагрузка валидированного JWT доступа, выпущенного Keycloak."""

    # sub — идентификатор пользователя в Keycloak (UUID)
    sub: str
    email: str | None
    roles: frozenset[str]
    # Отображаемое имя из профиля identity provider'а (Google): claim name/given_name.
    # Заполнено только при входе через соцсеть; при входе по паролю — None
    full_name: str | None = None
