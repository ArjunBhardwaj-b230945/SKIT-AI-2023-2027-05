
import pytest
from fastapi.testclient import TestClient

from main import app
from controllers import auth as auth_controller

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_users():
    auth_controller.users.clear()
    auth_controller.next_user_id = 1
    yield
    auth_controller.users.clear()
    auth_controller.next_user_id = 1


def test_signup_success():
    response = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "user"
    assert "password" not in data


def test_signup_duplicate_email():
    payload = {
        "email": "test@example.com",
        "password": "password123",
    }

    first = client.post("/auth/signup", json=payload)
    second = client.post("/auth/signup", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_signup_does_not_allow_admin_role():
    response = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_login_success():
    client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_wrong_password():
    client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


def test_authenticated_profile():
    client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    login = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    token = login.json()["access_token"]
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_profile_requires_authentication():
    response = client.get("/auth/me")
    assert response.status_code == 401
