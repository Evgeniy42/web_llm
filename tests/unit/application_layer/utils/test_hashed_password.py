import pytest

from app.application_layer.utils.hashed_password import (
    MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    hash_password,
    verify_password,
)
from tests.resources.mocks import TEST_PASSWORD
from tests.resources.users import LONG_PASSWORD


class TestHashPassword:
    def test_hash_password_success(self):
        result = hash_password(TEST_PASSWORD)

        assert result != TEST_PASSWORD
        assert result.startswith("$2b$")

    def test_hash_password_too_long(self):
        with pytest.raises(PasswordTooLongError):
            hash_password(LONG_PASSWORD)

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
        hashed = hash_password(TEST_PASSWORD)

        assert verify_password(TEST_PASSWORD, hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password(TEST_PASSWORD)

        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_too_long_returns_false(self):
        assert verify_password(LONG_PASSWORD, "$2b$12$fake") is False
