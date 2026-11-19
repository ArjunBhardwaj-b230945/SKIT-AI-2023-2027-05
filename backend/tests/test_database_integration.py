import pytest
from sqlalchemy import select

from database import check_database_connectivity, session_scope, SessionLocal
from models.user import User
from models.tax_record import TaxRecord
from models.chat import ChatMessageModel
from models.audit_log import AuditLogModel
from controllers.audit import record_audit_event
from controllers.database_ops import verify_user_cascade_status


def get_auth_token(client, email="dbtest@example.com", password="password123"):
    """Register and login helper returning access token."""
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


def test_database_connectivity_and_pool_status(client):
    """Verify refined database connection checking and pool diagnostics."""
    status_data = check_database_connectivity()
    assert status_data["status"] == "connected"
    assert "latency_ms" in status_data
    assert status_data["latency_ms"] >= 0.0


def test_session_scope_atomic_commit(client):
    """Verify that session_scope commits database changes upon successful block exit."""
    test_email = "scope_commit@example.com"
    with session_scope() as db:
        user = User(email=test_email, password="hashed_test_password", role="user")
        db.add(user)

    with SessionLocal() as db:
        saved_user = db.scalar(select(User).where(User.email == test_email))
        assert saved_user is not None
        assert saved_user.email == test_email


def test_session_scope_atomic_rollback_on_exception(client):
    """Verify that session_scope rolls back changes when an exception is raised."""
    test_email = "scope_rollback@example.com"
    with pytest.raises(ValueError):
        with session_scope() as db:
            user = User(email=test_email, password="hashed_test_password", role="user")
            db.add(user)
            db.flush()  # sends INSERT to transaction
            raise ValueError("Forced error to test atomic rollback")

    with SessionLocal() as db:
        aborted_user = db.scalar(select(User).where(User.email == test_email))
        assert aborted_user is None


def test_foreign_key_cascades_on_user_deletion(client):
    """
    Verify database referential integrity and ON DELETE CASCADE:
    Deleting a user automatically removes dependent tax records and chat messages.
    """
    token = get_auth_token(client, "cascade_user@example.com")

    # 1. Create a tax record linked to this user
    tax_payload = {
        "pan_number": "ABCDE1234F",
        "financial_year": "2024-25",
        "assessment_year": "2025-26",
        "tax_regime": "new",
        "filing_status": "draft",
        "gross_total_income": 900000.0,
        "taxable_income": 825000.0,
        "total_tax_payable": 37500.0,
    }
    client.post("/tax-records", json=tax_payload, headers=auth_headers(token))

    # 2. Create a chat message linked to this user
    client.post("/chat", json={"message": "Cascade test query"}, headers=auth_headers(token))

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "cascade_user@example.com"))
        user_id = user.id
        status_before = verify_user_cascade_status(db, user_id)
        assert status_before["tax_records_count"] == 1
        assert status_before["chat_messages_count"] == 2  # user + assistant

    # 3. Delete the user
    del_resp = client.delete(f"/auth/users/{user_id}", headers=auth_headers(token))
    assert del_resp.status_code == 200

    # 4. Verify cascade cleaned up dependent records
    with SessionLocal() as db:
        orphan_tax = db.scalars(select(TaxRecord).where(TaxRecord.user_id == user_id)).all()
        orphan_chat = db.scalars(select(ChatMessageModel).where(ChatMessageModel.user_id == user_id)).all()
        assert len(orphan_tax) == 0
        assert len(orphan_chat) == 0


def test_audit_log_tracking_and_user_retrieval(client):
    """Verify database operation audit logging and user endpoint retrieval."""
    token = get_auth_token(client, "audit_test@example.com")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "audit_test@example.com"))
        record_audit_event(
            db=db,
            action="RECORD_UPDATE",
            entity_type="TaxRecord",
            user_id=user.id,
            entity_id=101,
            details={"field": "filing_status", "new_value": "computed"},
            ip_address="127.0.0.1",
        )

    response = client.get("/audit/my-logs", headers=auth_headers(token))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["logs"][0]["action"] == "RECORD_UPDATE"
    assert data["logs"][0]["entity_type"] == "TaxRecord"


def test_database_diagnostics_api_endpoint(client):
    """Test the detailed database health and diagnostics endpoint."""
    response = client.get("/database/diagnostics")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "latency_ms" in data
    assert "table_counts" in data
    assert "users" in data["table_counts"]
    assert "tax_records" in data["table_counts"]
    assert "chat_messages" in data["table_counts"]
