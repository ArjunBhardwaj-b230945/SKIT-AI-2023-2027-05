
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


def create_account(email, password="password123"):
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def login(email, password="password123"):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_regular_user_cannot_list_all_users():
    create_account("user@example.com")
    token = login("user@example.com")

    response = client.get(
        "/auth/users",
        headers=auth_header(token),
    )

    assert response.status_code == 403


def test_user_can_update_own_email():
    user = create_account("user@example.com")
    token = login("user@example.com")

    response = client.put(
        f"/auth/users/{user['id']}",
        json={"email": "updated@example.com"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["email"] == "updated@example.com"


def test_user_cannot_update_another_users_email():
    first = create_account("first@example.com")
    create_account("second@example.com")
    token = login("first@example.com")

    response = client.put(
        f"/auth/users/{first['id'] + 1}",
        json={"email": "changed@example.com"},
        headers=auth_header(token),
    )

    assert response.status_code == 403


def test_user_can_change_password():
    user = create_account("user@example.com")
    token = login("user@example.com")

    response = client.put(
        f"/auth/users/{user['id']}/password",
        json={
            "current_password": "password123",
            "new_password": "newpassword123",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 200

    old_login = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "password123",
        },
    )
    new_login = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "newpassword123",
        },
    )

    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_wrong_current_password_rejected():
    user = create_account("user@example.com")
    token = login("user@example.com")

    response = client.put(
        f"/auth/users/{user['id']}/password",
        json={
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 400


def test_user_can_delete_own_account():
    user = create_account("user@example.com")
    token = login("user@example.com")

    response = client.delete(
        f"/auth/users/{user['id']}",
        headers=auth_header(token),
    )

    assert response.status_code == 200

    profile = client.get(
        "/auth/me",
        headers=auth_header(token),
    )

    assert profile.status_code == 401


def test_admin_can_list_users():
    create_account("user@example.com")

    # Create an admin through the trusted internal controller,
    # not through the public signup endpoint.
    auth_controller.create_user(
        email="admin@example.com",
        password="adminpassword123",
        role="admin",
    )

    token = login("admin@example.com", "adminpassword123")

    response = client.get(
        "/auth/users",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
