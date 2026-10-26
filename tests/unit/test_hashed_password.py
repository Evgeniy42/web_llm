import pytest

from app.application_layer.utils.hashed_password import (
    MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    hash_password,
    verify_password,
)


class TestHashPassword:
    def test_hash_password_success(self):
        result = hash_password("password123")

        assert result != "password123"
        assert result.startswith("$2b$")

    def test_hash_password_too_long(self):
        long_password = "я" * 40  # 80 байт в UTF-8

        with pytest.raises(PasswordTooLongError):
            hash_password(long_password)

    def test_hash_password_max_bytes_boundary(self):
        # Ровно 72 байта — допустимо
        password = "a" * MAX_PASSWORD_BYTES
        result = hash_password(password)
        assert result.startswith("$2b$")

    def test_hash_password_exceeds_max_bytes(self):
        password = "a" * (MAX_PASSWORD_BYTES + 1)
        with pytest.raises(PasswordTooLongError):
            hash_password(password)


class TestVerifyPassword:
    def test_verify_password_correct(self):
        hashed = hash_password("password123")

        assert verify_password("password123", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("password123")

        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_too_long_returns_false(self):
        long_password = "я" * 40

        assert verify_password(long_password, "$2b$12$fake") is False
