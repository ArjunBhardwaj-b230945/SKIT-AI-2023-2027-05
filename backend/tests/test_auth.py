import pytest

from fastapi.testclient import TestClient

from main import app
from controllers import auth as auth_controller


# ============================================================
# Test Client
# ============================================================

client = TestClient(app)


# ============================================================
# Test Setup
# ============================================================

@pytest.fixture(autouse=True)
def reset_user_storage():
    """
    Reset temporary user storage before every test.

    This keeps test cases independent and avoids failures
    caused by users created by previous tests.
    """

    auth_controller.users.clear()
    auth_controller.next_user_id = 1

    yield

    auth_controller.users.clear()
    auth_controller.next_user_id = 1


# ============================================================
# Test Helpers
# ============================================================

def register_user(
    email="user@example.com",
    password="password123"
):
    """
    Register a standard user through the public API.
    """

    return client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password
        }
    )


def login_user(
    email="user@example.com",
    password="password123"
):
    """
    Authenticate a user and return the response.
    """

    return client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password
        }
    )


def authorization_headers(token: str) -> dict:
    """
    Format a JWT as a Bearer authorization header.
    """

    return {
        "Authorization": f"Bearer {token}"
    }


def create_admin_token() -> str:
    """
    Create a development administrator and return a token.

    This helper is for automated tests only. It does not
    expose administrator creation through a public route.
    """

    admin = auth_controller.create_user(
        email="admin@example.com",
        password="adminpassword123",
        role="admin"
    )

    return auth_controller.create_access_token(
        admin
    )


# ============================================================
# Registration Tests
# ============================================================

def test_user_registration_success():
    """
    A valid user should be registered successfully.
    """

    response = register_user()

    assert response.status_code == 201

    data = response.json()

    assert data["success"] is True
    assert data["user"]["email"] == "user@example.com"
    assert data["user"]["role"] == "user"
    assert "password" not in data["user"]


def test_duplicate_registration_is_rejected():
    """
    Duplicate email addresses should not create extra users.
    """

    first_response = register_user()
    second_response = register_user()

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_public_registration_cannot_assign_admin():
    """
    An extra role field in the public request must not
    grant administrator privileges.
    """

    response = client.post(
        "/auth/signup",
        json={
            "email": "newuser@example.com",
            "password": "password123",
            "role": "admin"
        }
    )

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "user"


# ============================================================
# Login Tests
# ============================================================

def test_login_returns_access_token():
    """
    Valid credentials should produce a Bearer access token.
    """

    register_user()

    response = login_user()

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 0


def test_login_rejects_wrong_password():
    """
    Incorrect credentials should return an unauthorized
    response without revealing account details.
    """

    register_user()

    response = login_user(
        password="incorrectpassword"
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email():
    """
    A user who has not registered cannot log in.
    """

    response = login_user(
        email="unknown@example.com"
    )

    assert response.status_code == 401


# ============================================================
# Authentication Tests
# ============================================================

def test_profile_requires_authentication():
    """
    Protected profile access should reject missing tokens.
    """

    response = client.get(
        "/auth/me"
    )

    assert response.status_code == 401


def test_profile_accepts_valid_token():
    """
    A valid token should identify the correct account.
    """

    register_user()

    login_response = login_user()

    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers=authorization_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "user@example.com"


def test_profile_rejects_invalid_token():
    """
    Malformed tokens should not grant protected access.
    """

    response = client.get(
        "/auth/me",
        headers=authorization_headers("not.a.valid.token")
    )

    assert response.status_code == 401


# ============================================================
# Authorization Tests
# ============================================================

def test_regular_user_cannot_list_all_users():
    """
    User listing is restricted to administrators.
    """

    register_user()

    token = login_user().json()["access_token"]

    response = client.get(
        "/auth/users",
        headers=authorization_headers(token)
    )

    assert response.status_code == 403


def test_admin_can_list_users():
    """
    Administrators should be allowed to list users.
    """

    register_user()

    token = create_admin_token()

    response = client.get(
        "/auth/users",
        headers=authorization_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_user_cannot_access_another_users_profile():
    """
    Users must not access profiles belonging to other users.
    """

    register_user(
        email="first@example.com"
    )

    register_user(
        email="second@example.com"
    )

    token = login_user(
        email="first@example.com"
    ).json()["access_token"]

    response = client.get(
        "/auth/users/2",
        headers=authorization_headers(token)
    )

    assert response.status_code == 403


def test_user_can_access_own_profile():
    """
    An authenticated user can retrieve their own profile.
    """

    register_user()

    token = login_user().json()["access_token"]

    response = client.get(
        "/auth/users/1",
        headers=authorization_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == 1


# ============================================================
# User Update Tests
# ============================================================

def test_user_can_update_own_email():
    """
    A user should be able to update their own email.
    """

    register_user()

    token = login_user().json()["access_token"]

    response = client.put(
        "/auth/users/1",
        headers=authorization_headers(token),
        json={
            "email": "updated@example.com"
        }
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "updated@example.com"


def test_user_cannot_update_another_users_email():
    """
    Ownership checks should prevent unauthorized updates.
    """

    register_user(
        email="first@example.com"
    )

    register_user(
        email="second@example.com"
    )

    token = login_user(
        email="first@example.com"
    ).json()["access_token"]

    response = client.put(
        "/auth/users/2",
        headers=authorization_headers(token),
        json={
            "email": "changed@example.com"
        }
    )

    assert response.status_code == 403


def test_user_cannot_change_own_role():
    """
    Public update requests must not expose role changes.
    """

    register_user()

    token = login_user().json()["access_token"]

    response = client.put(
        "/auth/users/1",
        headers=authorization_headers(token),
        json={
            "role": "admin"
        }
    )

    # The request contains no allowed update fields.
    assert response.status_code == 400


# ============================================================
# User Deletion Tests
# ============================================================

def test_user_can_delete_own_account():
    """
    An authenticated user can delete their own account.
    """

    register_user()

    token = login_user().json()["access_token"]

    response = client.delete(
        "/auth/users/1",
        headers=authorization_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_user_cannot_delete_another_account():
    """
    Users cannot delete accounts they do not own.
    """

    register_user(
        email="first@example.com"
    )

    register_user(
        email="second@example.com"
    )

    token = login_user(
        email="first@example.com"
    ).json()["access_token"]

    response = client.delete(
        "/auth/users/2",
        headers=authorization_headers(token)
    )

    assert response.status_code == 403


def test_deleted_user_token_is_rejected():
    """
    A deleted account should no longer be accepted by
    the current-user authentication dependency.
    """

    register_user()

    token = login_user().json()["access_token"]

    delete_response = client.delete(
        "/auth/users/1",
        headers=authorization_headers(token)
    )

    assert delete_response.status_code == 200

    profile_response = client.get(
        "/auth/me",
        headers=authorization_headers(token)
    )

    assert profile_response.status_code == 401