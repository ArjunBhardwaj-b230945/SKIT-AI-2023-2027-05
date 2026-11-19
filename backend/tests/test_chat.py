import pytest


def get_auth_token(client, email="chatuser@example.com", password="password123"):
    """Helper to register and log in a user for authenticated testing."""
    client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    return login_resp.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_send_chat_message_success(client):
    """Test sending a standard tax query to the AI assistant."""
    token = get_auth_token(client, "chat1@example.com")
    payload = {
        "message": "What is the standard deduction in the New Tax Regime for FY 2024-25?",
        "financial_year": "2024-25",
        "regime_preference": "new",
    }

    response = client.post(
        "/chat",
        json=payload,
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data
    assert len(data["session_id"]) > 0
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert "citations" in data
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0


def test_multiturn_conversation_continuity(client):
    """Test maintaining conversation context across multiple turns using session_id."""
    token = get_auth_token(client, "chat2@example.com")

    # Turn 1: Ask about regimes
    turn1_payload = {
        "message": "Compare old vs new tax regime for 12 lakh salary",
    }
    resp1 = client.post("/chat", json=turn1_payload, headers=auth_headers(token))
    assert resp1.status_code == 200
    session_id = resp1.json()["session_id"]
    reply1 = resp1.json()["reply"]

    # Turn 2: Follow-up question using the same session_id and history
    turn2_payload = {
        "message": "What if I have 80C deductions of 1.5 lakhs?",
        "session_id": session_id,
        "conversation_history": [
            {"role": "user", "content": turn1_payload["message"]},
            {"role": "assistant", "content": reply1},
        ],
    }
    resp2 = client.post("/chat", json=turn2_payload, headers=auth_headers(token))
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == session_id
    assert "80C" in resp2.json()["reply"] or "deduction" in resp2.json()["reply"].lower()


def test_retrieve_chat_session_history(client):
    """Test loading historical conversation messages for a specific session."""
    token = get_auth_token(client, "chat3@example.com")

    # Send a message to create history
    resp = client.post(
        "/chat",
        json={"message": "Can I claim HRA exemption without rent receipts?"},
        headers=auth_headers(token),
    )
    session_id = resp.json()["session_id"]

    # Retrieve history
    history_resp = client.get(
        f"/chat/history/{session_id}",
        headers=auth_headers(token),
    )
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["session_id"] == session_id
    assert history_data["total_messages"] >= 2  # user message + assistant reply
    roles = [m["role"] for m in history_data["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_list_user_chat_sessions(client):
    """Test listing all active conversation sessions for the user."""
    token = get_auth_token(client, "chat4@example.com")

    # Create two separate conversation sessions
    client.post("/chat", json={"message": "What is ITR-1 Sahaj?"}, headers=auth_headers(token))
    client.post("/chat", json={"message": "What is Section 80D health insurance?"}, headers=auth_headers(token))

    sessions_resp = client.get("/chat/sessions", headers=auth_headers(token))
    assert sessions_resp.status_code == 200
    sessions_list = sessions_resp.json()
    assert len(sessions_list) == 2
    for s in sessions_list:
        assert "session_id" in s
        assert "last_message" in s
        assert s["message_count"] >= 2


def test_clear_session_history(client):
    """Test deleting conversation history for a given session."""
    token = get_auth_token(client, "chat5@example.com")

    resp = client.post(
        "/chat",
        json={"message": "How to reconcile Form 16 and 26AS?"},
        headers=auth_headers(token),
    )
    session_id = resp.json()["session_id"]

    # Delete history
    del_resp = client.delete(
        f"/chat/history/{session_id}",
        headers=auth_headers(token),
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Subsequent fetch returns 404
    fetch_resp = client.get(
        f"/chat/history/{session_id}",
        headers=auth_headers(token),
    )
    assert fetch_resp.status_code == 404


def test_chat_unauthorized_without_token(client):
    """Verify that unauthenticated chat requests are rejected with 401."""
    response = client.post(
        "/chat",
        json={"message": "What is the tax rate?"},
    )
    assert response.status_code == 401


def test_chat_empty_message_rejected(client):
    """Verify that empty message bodies are rejected with 422 Unprocessable Entity."""
    token = get_auth_token(client, "chat6@example.com")
    response = client.post(
        "/chat",
        json={"message": ""},  # empty string violates min_length=1
        headers=auth_headers(token),
    )
    assert response.status_code == 422


def test_chat_user_isolation(client):
    """Verify that User B cannot view or delete User A's conversation history."""
    token_a = get_auth_token(client, "user_chat_a@example.com")
    token_b = get_auth_token(client, "user_chat_b@example.com")

    resp_a = client.post(
        "/chat",
        json={"message": "User A confidential tax question"},
        headers=auth_headers(token_a),
    )
    session_id_a = resp_a.json()["session_id"]

    # User B tries to view User A's session
    get_resp = client.get(
        f"/chat/history/{session_id_a}",
        headers=auth_headers(token_b),
    )
    assert get_resp.status_code == 404

    # User B tries to delete User A's session
    del_resp = client.delete(
        f"/chat/history/{session_id_a}",
        headers=auth_headers(token_b),
    )
    assert del_resp.status_code == 404
