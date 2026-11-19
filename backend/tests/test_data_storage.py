import pytest


def get_auth_token(client, email="taxuser@example.com", password="password123"):
    """Helper fixture function to create a user and obtain a JWT bearer token."""
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


def sample_tax_payload():
    return {
        "pan_number": "ABCDE1234F",
        "financial_year": "2023-24",
        "assessment_year": "2024-25",
        "tax_regime": "new",
        "filing_status": "draft",
        "gross_total_income": 1250000.0,
        "total_deductions": 50000.0,
        "taxable_income": 1200000.0,
        "total_tax_payable": 95000.0,
        "computation_details": {
            "salary": 1250000.0,
            "standard_deduction": 50000.0,
            "slab_breakdown": [
                {"slab": "0-3L", "tax": 0.0},
                {"slab": "3L-6L", "tax": 15000.0},
                {"slab": "6L-9L", "tax": 30000.0},
                {"slab": "9L-12L", "tax": 45000.0},
            ],
            "cess": 3800.0,
        },
        "notes": "Computed using new regime defaults for FY 2023-24",
    }


def test_store_tax_record_success(client):
    """Test storing a new tax record into the database."""
    token = get_auth_token(client, "store_test@example.com")
    payload = sample_tax_payload()

    response = client.post(
        "/tax-records",
        json=payload,
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["pan_number"] == "ABCDE1234F"
    assert data["assessment_year"] == "2024-25"
    assert data["taxable_income"] == 1200000.0
    assert data["total_tax_payable"] == 95000.0
    assert data["computation_details"]["salary"] == 1250000.0
    assert "created_at" in data
    assert "updated_at" in data


def test_retrieve_tax_record_by_id(client):
    """Test retrieving a previously stored record by its ID."""
    token = get_auth_token(client, "retrieve_test@example.com")
    payload = sample_tax_payload()

    create_resp = client.post(
        "/tax-records",
        json=payload,
        headers=auth_headers(token),
    )
    record_id = create_resp.json()["id"]

    retrieve_resp = client.get(
        f"/tax-records/{record_id}",
        headers=auth_headers(token),
    )

    assert retrieve_resp.status_code == 200
    retrieved_data = retrieve_resp.json()
    assert retrieved_data["id"] == record_id
    assert retrieved_data["pan_number"] == "ABCDE1234F"
    assert retrieved_data["gross_total_income"] == 1250000.0


def test_retrieve_user_tax_records_list_and_pagination(client):
    """Test retrieving a list of user tax records with pagination."""
    token = get_auth_token(client, "list_test@example.com")

    # Store 3 records with different assessment years
    years = ["2022-23", "2023-24", "2024-25"]
    for yr in years:
        p = sample_tax_payload()
        p["assessment_year"] = yr
        client.post("/tax-records", json=p, headers=auth_headers(token))

    # Retrieve all
    response = client.get("/tax-records", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["records"]) == 3

    # Retrieve with limit=2
    paginated_resp = client.get("/tax-records?limit=2&skip=0", headers=auth_headers(token))
    assert paginated_resp.status_code == 200
    paginated_body = paginated_resp.json()
    assert paginated_body["total"] == 3
    assert len(paginated_body["records"]) == 2
    assert paginated_body["page"] == 1


def test_retrieve_records_with_filter(client):
    """Test filtering stored records by assessment year and status."""
    token = get_auth_token(client, "filter_test@example.com")

    p1 = sample_tax_payload()
    p1["assessment_year"] = "2023-24"
    p1["filing_status"] = "draft"
    client.post("/tax-records", json=p1, headers=auth_headers(token))

    p2 = sample_tax_payload()
    p2["assessment_year"] = "2024-25"
    p2["filing_status"] = "computed"
    client.post("/tax-records", json=p2, headers=auth_headers(token))

    # Filter by assessment_year 2024-25
    resp = client.get("/tax-records?assessment_year=2024-25", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["records"][0]["assessment_year"] == "2024-25"

    # Filter by filing_status computed
    resp_status = client.get("/tax-records?filing_status=computed", headers=auth_headers(token))
    assert resp_status.status_code == 200
    assert resp_status.json()["total"] == 1
    assert resp_status.json()["records"][0]["filing_status"] == "computed"


def test_update_stored_tax_record(client):
    """Test updating fields of an existing persisted record."""
    token = get_auth_token(client, "update_test@example.com")
    payload = sample_tax_payload()

    create_resp = client.post("/tax-records", json=payload, headers=auth_headers(token))
    record_id = create_resp.json()["id"]

    update_payload = {
        "filing_status": "computed",
        "taxable_income": 1150000.0,
        "total_tax_payable": 88000.0,
        "notes": "Updated after incorporating 80CCD deduction",
    }

    put_resp = client.put(
        f"/tax-records/{record_id}",
        json=update_payload,
        headers=auth_headers(token),
    )

    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["filing_status"] == "computed"
    assert updated_data["taxable_income"] == 1150000.0
    assert updated_data["total_tax_payable"] == 88000.0
    assert updated_data["notes"] == "Updated after incorporating 80CCD deduction"


def test_delete_stored_tax_record(client):
    """Test removing a stored tax record from the database."""
    token = get_auth_token(client, "delete_test@example.com")
    payload = sample_tax_payload()

    create_resp = client.post("/tax-records", json=payload, headers=auth_headers(token))
    record_id = create_resp.json()["id"]

    del_resp = client.delete(f"/tax-records/{record_id}", headers=auth_headers(token))
    assert del_resp.status_code == 200

    # Ensure subsequent retrieval returns 404
    get_resp = client.get(f"/tax-records/{record_id}", headers=auth_headers(token))
    assert get_resp.status_code == 404


def test_user_data_isolation(client):
    """Verify that User B cannot access or modify records created by User A."""
    token_a = get_auth_token(client, "user_a@example.com")
    token_b = get_auth_token(client, "user_b@example.com")

    # User A stores a record
    create_resp = client.post(
        "/tax-records",
        json=sample_tax_payload(),
        headers=auth_headers(token_a),
    )
    record_id = create_resp.json()["id"]

    # User B attempts to retrieve User A's record
    get_resp = client.get(
        f"/tax-records/{record_id}",
        headers=auth_headers(token_b),
    )
    assert get_resp.status_code == 403

    # User B attempts to update User A's record
    put_resp = client.put(
        f"/tax-records/{record_id}",
        json={"notes": "Hacked"},
        headers=auth_headers(token_b),
    )
    assert put_resp.status_code == 403

    # User B attempts to delete User A's record
    del_resp = client.delete(
        f"/tax-records/{record_id}",
        headers=auth_headers(token_b),
    )
    assert del_resp.status_code == 403


def test_retrieve_user_tax_summary(client):
    """Test retrieving aggregated storage statistics for the user."""
    token = get_auth_token(client, "summary_test@example.com")

    p1 = sample_tax_payload()
    p1["filing_status"] = "draft"
    p1["total_tax_payable"] = 50000.0
    p1["assessment_year"] = "2023-24"
    client.post("/tax-records", json=p1, headers=auth_headers(token))

    p2 = sample_tax_payload()
    p2["filing_status"] = "computed"
    p2["total_tax_payable"] = 75000.0
    p2["assessment_year"] = "2024-25"
    client.post("/tax-records", json=p2, headers=auth_headers(token))

    summary_resp = client.get("/tax-records/summary", headers=auth_headers(token))
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_records"] == 2
    assert summary["draft_count"] == 1
    assert summary["computed_count"] == 1
    assert summary["total_tax_payable_sum"] == 125000.0
    assert "2023-24" in summary["recorded_assessment_years"]
    assert "2024-25" in summary["recorded_assessment_years"]


def test_invalid_pan_format_rejected(client):
    """Test schema validation rejection for malformed PAN string."""
    token = get_auth_token(client, "pan_val_test@example.com")
    payload = sample_tax_payload()
    payload["pan_number"] = "INVALID12"  # Invalid length & format

    response = client.post(
        "/tax-records",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 422
