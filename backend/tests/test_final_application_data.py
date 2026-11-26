import pytest
from database_seed import seed_database


def get_auth_token(client, email="appuser@example.com", password="password123"):
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


def test_tax_computation_regime_comparison(client):
    """Test dual regime tax calculation and recommendation engine."""
    token = get_auth_token(client, "calc_user@example.com")
    payload = {
        "assessment_year": "2025-26",
        "financial_year": "2024-25",
        "salary": {
            "gross_salary": 1200000.0,
            "hra_received": 180000.0,
            "actual_rent_paid": 240000.0,
            "is_metro_city": True,
        },
        "deductions": {
            "section_80c": 150000.0,
            "section_80d_self_family": 25000.0,
            "section_80ccd_1b": 50000.0,
        },
        "taxes_paid": {
            "tds_salary": 90000.0,
        },
    }

    response = client.post("/tax/compute", json=payload, headers=auth_headers(token))
    assert response.status_code == 200
    data = response.json()
    assert "recommended_regime" in data
    assert "tax_savings_with_recommended" in data
    assert "new_regime" in data
    assert "old_regime" in data
    assert data["new_regime"]["gross_total_income"] == 1200000.0
    assert data["new_regime"]["standard_deduction"] == 75000.0
    assert data["old_regime"]["standard_deduction"] == 50000.0


def test_document_reconciliation_pass_and_mismatch(client):
    """Test Form 16 vs Form 26AS document cross-validation."""
    token = get_auth_token(client, "recon_user@example.com")

    # Case 1: Matching documents
    match_payload = {
        "employee_pan": "ABCDE1234F",
        "form16_tds": 75000.0,
        "form26as_pan": "ABCDE1234F",
        "form26as_tds": 75000.0,
    }
    resp1 = client.post("/tax/reconcile-documents", json=match_payload, headers=auth_headers(token))
    assert resp1.status_code == 200
    assert resp1.json()["pan_match"] is True
    assert resp1.json()["tds_match"] is True
    assert resp1.json()["can_proceed"] is True

    # Case 2: PAN mismatch
    mismatch_payload = {
        "employee_pan": "ABCDE1234F",
        "form16_tds": 75000.0,
        "form26as_pan": "XYZWQ9999K",
        "form26as_tds": 75000.0,
    }
    resp2 = client.post("/tax/reconcile-documents", json=mismatch_payload, headers=auth_headers(token))
    assert resp2.status_code == 200
    assert resp2.json()["pan_match"] is False
    assert resp2.json()["can_proceed"] is False
    assert len(resp2.json()["validation_flags"]) >= 1


def test_tax_profile_persistence(client):
    """Test storing and listing taxpayer profiles in PostgreSQL."""
    token = get_auth_token(client, "profile_user@example.com")
    profile_payload = {
        "assessment_year": "2025-26",
        "financial_year": "2024-25",
        "pan_number": "ABCDE1234F",
        "full_name": "Test Taxpayer",
        "date_of_birth": "1992-08-20",
        "aadhaar_last_four": "1234",
        "salary_income": 1100000.0,
        "total_deductions": 150000.0,
        "recommended_regime": "new",
        "total_tax": 75000.0,
        "refund_due": 5000.0,
    }

    create_resp = client.post("/tax/profiles", json=profile_payload, headers=auth_headers(token))
    assert create_resp.status_code == 201
    assert create_resp.json()["id"] is not None
    assert create_resp.json()["full_name"] == "Test Taxpayer"

    list_resp = client.get("/tax/profiles", headers=auth_headers(token))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


def test_submit_and_list_itr_filings(client):
    """Test officially finalizing and storing an ITR filing in the database."""
    token = get_auth_token(client, "filing_user@example.com")
    filing_payload = {
        "assessment_year": "2025-26",
        "financial_year": "2024-25",
        "pan_number": "ABCDE1234F",
        "itr_type": "ITR-1",
        "gross_total_income": 1200000.0,
        "total_deductions": 75000.0,
        "taxable_income": 1125000.0,
        "total_tax_payable": 82500.0,
        "taxes_paid": 95000.0,
        "refund_or_payable": 12500.0,
        "verification_mode": "aadhaar_otp",
    }

    submit_resp = client.post("/itr/submit", json=filing_payload, headers=auth_headers(token))
    assert submit_resp.status_code == 201
    data = submit_resp.json()
    assert data["acknowledgement_number"].startswith("ACK202526")
    assert data["filing_status"] == "submitted"
    assert data["refund_or_payable"] == 12500.0

    # List filings
    list_resp = client.get("/itr/filings", headers=auth_headers(token))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["acknowledgement_number"] == data["acknowledgement_number"]


def test_application_dashboard_aggregation(client):
    """Test unified application dashboard telemetry."""
    token = get_auth_token(client, "dash_user@example.com")

    # Submit an ITR
    filing_payload = {
        "assessment_year": "2025-26",
        "financial_year": "2024-25",
        "pan_number": "ABCDE1234F",
        "gross_total_income": 1000000.0,
        "taxable_income": 925000.0,
        "total_tax_payable": 52500.0,
        "taxes_paid": 60000.0,
        "refund_or_payable": 7500.0,
    }
    client.post("/itr/submit", json=filing_payload, headers=auth_headers(token))

    # Send a chat message
    client.post("/chat", json={"message": "Dashboard query"}, headers=auth_headers(token))

    dash_resp = client.get("/application/dashboard", headers=auth_headers(token))
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["total_filings_submitted"] == 1
    assert dash_data["total_refund_claimed"] == 7500.0
    assert dash_data["active_chat_sessions"] >= 1
    assert dash_data["latest_acknowledgement_number"] is not None


def test_application_data_export(client):
    """Test comprehensive application data portfolio export."""
    token = get_auth_token(client, "export_user@example.com")

    # Add a tax record
    client.post(
        "/tax-records",
        json={
            "pan_number": "ABCDE1234F",
            "financial_year": "2024-25",
            "assessment_year": "2025-26",
            "tax_regime": "new",
            "filing_status": "draft",
            "gross_total_income": 800000.0,
            "taxable_income": 725000.0,
            "total_tax_payable": 27500.0,
        },
        headers=auth_headers(token),
    )

    export_resp = client.get("/application/export", headers=auth_headers(token))
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "user" in export_data
    assert "tax_records" in export_data
    assert len(export_data["tax_records"]) == 1
    assert "itr_filings" in export_data
    assert "exported_at" in export_data


def test_database_seed_utility_execution(client):
    """Verify that database seeding utility provisions application baseline without errors."""
    counts = seed_database()
    assert counts["users"] >= 1
    assert counts["profiles"] >= 1
    assert counts["filings"] >= 1
