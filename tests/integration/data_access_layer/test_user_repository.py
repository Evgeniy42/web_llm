import pytest
from sqlalchemy.exc import IntegrityError

from app.data_access_layer.repositories.user_repository import UserRepository
from tests.resources.api import EMAIL_KEY, USERNAME_KEY
from tests.resources.users import STUB_HASHED_PASSWORD, TEST_USER_1, TEST_USER_2


@pytest.fixture
async def user_repo(db_session):
    return UserRepository(db_session)


class TestUserRepository:
    async def test_create_and_get_user(self, user_repo):
        user = await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_1[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )

        assert user.id is not None
        assert user.username == TEST_USER_1[USERNAME_KEY]
        assert user.email == TEST_USER_1[EMAIL_KEY]

        found = await user_repo.get_user_by_id(user.id)
        assert found is not None
        assert found.username == TEST_USER_1[USERNAME_KEY]

    async def test_get_user_by_email(self, user_repo):
        await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_1[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )

        found = await user_repo.get_user_by_email(TEST_USER_1[EMAIL_KEY])
        assert found is not None
        assert found.email == TEST_USER_1[EMAIL_KEY]

    async def test_duplicate_username_allowed(self, user_repo):
        await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_1[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )

        user2 = await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_2[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )
        assert user2.username == TEST_USER_1[USERNAME_KEY]

    async def test_duplicate_email_raises_integrity_error(self, user_repo, db_session):
        await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_1[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )

        with pytest.raises(IntegrityError):
            await user_repo.create_user(
                username=TEST_USER_2[USERNAME_KEY],
                email=TEST_USER_1[EMAIL_KEY],
                password=STUB_HASHED_PASSWORD,
            )
        await db_session.rollback()

    async def test_update_user(self, user_repo):
        user = await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_1[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )

        updated = await user_repo.update_user(user.id, username="updated_name")
        assert updated is not None
        assert updated.username == "updated_name"
        assert updated.email == TEST_USER_1[EMAIL_KEY]

    async def test_update_user_not_found(self, user_repo):
        result = await user_repo.update_user(999999, username="nonexistent")
        assert result is None

    async def test_delete_user(self, user_repo):
        user = await user_repo.create_user(
            username=TEST_USER_1[USERNAME_KEY],
            email=TEST_USER_1[EMAIL_KEY],
            password=STUB_HASHED_PASSWORD,
        )

        assert await user_repo.delete_user(user.id) is True
        assert await user_repo.get_user_by_id(user.id) is None

    async def test_delete_user_not_found(self, user_repo):
        assert await user_repo.delete_user(999999) is False
