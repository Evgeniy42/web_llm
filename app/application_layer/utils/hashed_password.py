import bcrypt

# bcrypt ограничивает пароль 72 байтами
MAX_PASSWORD_BYTES: int = 72


class PasswordTooLongError(ValueError):
    """Пароль превышает допустимую длину в байтах."""

    def __init__(self, length: int, max_length: int = MAX_PASSWORD_BYTES):
        self.length = length
        self.max_length = max_length
        super().__init__(
            f"Password is {length} bytes, exceeds maximum of {max_length} bytes"
        )


def _validate_password_length(password: str) -> bytes:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(len(password_bytes))
    return password_bytes


def hash_password(password: str) -> str:
    password_bytes = _validate_password_length(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed: str) -> bool:
    try:
        password_bytes = _validate_password_length(plain_password)
    except PasswordTooLongError:
        return False
    return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))
