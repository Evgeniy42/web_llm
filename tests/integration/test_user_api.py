import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.configuration.database import get_db
from app.data_access_layer.models.base import Base
from app.data_access_layer.models.UserModel import User


# SQLite in-memory для тестов
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestUserEndpoints:
    def test_register_user_success(self, client):
        # Act
        response = client.post("/user/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "password" not in data

    def test_register_duplicate_email(self, client):
        # Arrange
        client.post("/user/register", json={
            "username": "user1",
            "email": "duplicate@example.com",
            "password": "password123"
        })

        # Act
        response = client.post("/user/register", json={
            "username": "user2",
            "email": "duplicate@example.com",
            "password": "password123"
        })

        # Assert
        assert response.status_code == 400

    def test_login_success(self, client):
        # Arrange
        client.post("/user/register", json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": "password123"
        })

        # Act
        response = client.post("/user/login", json={
            "email": "login@example.com",
            "password": "password123"
        })

        # Assert
        assert response.status_code == 200
        assert response.json()["email"] == "login@example.com"

    def test_login_wrong_password(self, client):
        # Arrange
        client.post("/user/register", json={
            "username": "wrongpass",
            "email": "wrong@example.com",
            "password": "password123"
        })

        # Act
        response = client.post("/user/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })

        # Assert
        assert response.status_code == 401

    def test_get_user_by_id(self, client):
        # Arrange
        register_response = client.post("/user/register", json={
            "username": "getbyid",
            "email": "getbyid@example.com",
            "password": "password123"
        })
        user_id = register_response.json()["id"]

        # Act
        response = client.get(f"/user/{user_id}")

        # Assert
        assert response.status_code == 200
        assert response.json()["username"] == "getbyid"

    def test_get_user_not_found(self, client):
        # Act
        response = client.get("/user/999")

        # Assert
        assert response.status_code == 404
