import pytest
from database import SessionLocal
from controllers import auth as auth_controller


def create_account(client, email, password="password123"):
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()


def login(client, email, password="password123"):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_regular_user_cannot_list_all_users(client):
    create_account(client, "user@example.com")
    token = login(client, "user@example.com")

    response = client.get(
        "/auth/users",
        headers=auth_header(token),
    )

    assert response.status_code == 403


def test_user_can_update_own_email(client):
    user = create_account(client, "user@example.com")
    token = login(client, "user@example.com")

    response = client.put(
        f"/auth/users/{user['id']}",
        json={"email": "updated@example.com"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["email"] == "updated@example.com"


def test_user_cannot_update_another_users_email(client):
    first = create_account(client, "first@example.com")
    create_account(client, "second@example.com")
    token = login(client, "first@example.com")

    response = client.put(
        f"/auth/users/{first['id'] + 1}",
        json={"email": "changed@example.com"},
        headers=auth_header(token),
    )

    assert response.status_code == 403


def test_user_can_change_password(client):
    user = create_account(client, "user@example.com")
    token = login(client, "user@example.com")

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


def test_wrong_current_password_rejected(client):
    user = create_account(client, "user@example.com")
    token = login(client, "user@example.com")

    response = client.put(
        f"/auth/users/{user['id']}/password",
        json={
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
        },
        headers=auth_header(token),
    )

    assert response.status_code == 400


def test_user_can_delete_own_account(client):
    user = create_account(client, "user@example.com")
    token = login(client, "user@example.com")

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


def test_admin_can_list_users(client):
    create_account(client, "user@example.com")

    # Create an admin through the trusted internal controller using DB session
    with SessionLocal() as db:
        auth_controller.create_user(
            db=db,
            email="admin@example.com",
            password="adminpassword123",
            role="admin",
        )

    token = login(client, "admin@example.com", "adminpassword123")

    response = client.get(
        "/auth/users",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
