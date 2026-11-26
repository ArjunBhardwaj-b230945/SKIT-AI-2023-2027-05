"""Create itr_filings table for finalized application data storage

Revision ID: 004_finalize_application_data
Revises: 003_refined_db_operations
Create Date: 2026-11-26 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004_finalize_application_data"
down_revision: Union[str, None] = "003_refined_db_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "itr_filings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("acknowledgement_number", sa.String(length=20), nullable=False),
        sa.Column("assessment_year", sa.String(length=9), nullable=False),
        sa.Column("financial_year", sa.String(length=9), nullable=False),
        sa.Column("itr_type", sa.String(length=10), nullable=False, server_default="ITR-1"),
        sa.Column("filing_status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("gross_total_income", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_deductions", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("taxable_income", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_tax_payable", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("taxes_paid", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("refund_or_payable", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("computation_payload", sa.Text(), nullable=True),
        sa.Column("verification_mode", sa.String(length=30), nullable=False, server_default="aadhaar_otp"),
        sa.Column("verification_status", sa.String(length=20), nullable=False, server_default="verified"),
        sa.Column("submission_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("acknowledgement_number"),
    )
    op.create_index(op.f("ix_itr_filings_id"), "itr_filings", ["id"], unique=False)
    op.create_index(op.f("ix_itr_filings_user_id"), "itr_filings", ["user_id"], unique=False)
    op.create_index(op.f("ix_itr_filings_acknowledgement_number"), "itr_filings", ["acknowledgement_number"], unique=True)
    op.create_index(op.f("ix_itr_filings_pan_number"), "itr_filings", ["pan_number"], unique=False)
    op.create_index(op.f("ix_itr_filings_assessment_year"), "itr_filings", ["assessment_year"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_itr_filings_assessment_year"), table_name="itr_filings")
    op.drop_index(op.f("ix_itr_filings_pan_number"), table_name="itr_filings")
    op.drop_index(op.f("ix_itr_filings_acknowledgement_number"), table_name="itr_filings")
    op.drop_index(op.f("ix_itr_filings_user_id"), table_name="itr_filings")
    op.drop_index(op.f("ix_itr_filings_id"), table_name="itr_filings")
    op.drop_table("itr_filings")
