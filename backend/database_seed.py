from datetime import datetime, timezone
import os
import sys

from sqlalchemy import select

from database import Base, SessionLocal, engine
from models.user import User
from models.tax_record import TaxRecord
from models.tax_profile import TaxProfileModel
from models.itr_filing import ITRFilingModel
from models.audit_log import AuditLogModel
from controllers.auth import hash_password


def seed_database() -> dict[str, int]:
    """
    Seed initial baseline application data into PostgreSQL.
    Creates schema tables and provisions default admin and sample test accounts.
    """
    Base.metadata.create_all(bind=engine)

    counts = {"users": 0, "profiles": 0, "records": 0, "filings": 0, "audit": 0}

    with SessionLocal() as db:
        # 1. Seed Default Admin User
        admin_email = "admin@taxsathi.com"
        admin = db.scalar(select(User).where(User.email == admin_email))
        if not admin:
            admin = User(
                email=admin_email,
                password=hash_password("Admin@123456"),
                role="admin",
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            counts["users"] += 1

        # 2. Seed Sample Regular User
        user_email = "demouser@taxsathi.com"
        user = db.scalar(select(User).where(User.email == user_email))
        if not user:
            user = User(
                email=user_email,
                password=hash_password("DemoUser@123"),
                role="user",
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            counts["users"] += 1

        # 3. Seed Sample Taxpayer Profile
        existing_profile = db.scalar(
            select(TaxProfileModel).where(TaxProfileModel.user_id == user.id)
        )
        if not existing_profile:
            profile = TaxProfileModel(
                user_id=user.id,
                assessment_year="2025-26",
                financial_year="2024-25",
                pan_number="ABCDE1234F",
                full_name="Demo Salaried Taxpayer",
                date_of_birth="1995-05-15",
                aadhaar_last_four="8899",
                bank_account_number="987654321012",
                bank_ifsc="HDFC0001234",
                address="Flat 402, Green Park Apartments, Jaipur, Rajasthan",
                salary_income=1200000.0,
                total_deductions=150000.0,
                recommended_regime="new",
                total_tax=82500.0,
                refund_due=17500.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(profile)
            counts["profiles"] += 1

        # 4. Seed Sample Tax Record
        existing_rec = db.scalar(
            select(TaxRecord).where(TaxRecord.user_id == user.id)
        )
        if not existing_rec:
            rec = TaxRecord(
                user_id=user.id,
                pan_number="ABCDE1234F",
                financial_year="2024-25",
                assessment_year="2025-26",
                tax_regime="new",
                filing_status="computed",
                gross_total_income=1200000.0,
                total_deductions=75000.0,
                taxable_income=1125000.0,
                total_tax_payable=82500.0,
                computation_details='{"gross_salary": 1200000, "std_deduction": 75000, "cess": 3300}',
                notes="Seed baseline calculation for FY 2024-25",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(rec)
            counts["records"] += 1

        # 5. Seed Sample Finalized ITR Filing
        existing_filing = db.scalar(
            select(ITRFilingModel).where(ITRFilingModel.user_id == user.id)
        )
        if not existing_filing:
            filing = ITRFilingModel(
                user_id=user.id,
                acknowledgement_number="ACK202526DEMO9901",
                assessment_year="2025-26",
                financial_year="2024-25",
                itr_type="ITR-1",
                filing_status="verified",
                pan_number="ABCDE1234F",
                gross_total_income=1200000.0,
                total_deductions=75000.0,
                taxable_income=1125000.0,
                total_tax_payable=82500.0,
                taxes_paid=100000.0,
                refund_or_payable=17500.0,
                computation_payload='{"regime": "new", "status": "verified"}',
                verification_mode="aadhaar_otp",
                verification_status="verified",
                submission_timestamp=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(filing)
            counts["filings"] += 1

        # 6. Seed Baseline Audit Log
        audit = AuditLogModel(
            user_id=user.id,
            action="DATABASE_SEED",
            entity_type="System",
            details="Baseline application data seeded successfully",
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        counts["audit"] += 1

        db.commit()

    return counts


if __name__ == "__main__":
    print("Seeding application database baseline data...")
    results = seed_database()
    print("Seed complete:", results)
