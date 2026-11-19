"""Add tax_profiles and audit_logs tables for refined database operations

Revision ID: 003_refined_db_operations
Revises: 002_add_chat_messages
Create Date: 2026-11-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003_refined_db_operations"
down_revision: Union[str, None] = "002_add_chat_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------
    # 1. Create 'tax_profiles' table
    # -------------------------------------------------------------
    op.create_table(
        "tax_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assessment_year", sa.String(length=9), nullable=False),
        sa.Column("financial_year", sa.String(length=9), nullable=False),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.String(length=10), nullable=True),
        sa.Column("aadhaar_last_four", sa.String(length=4), nullable=True),
        sa.Column("bank_account_number", sa.String(length=30), nullable=True),
        sa.Column("bank_ifsc", sa.String(length=11), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("salary_income", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_deductions", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("recommended_regime", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("total_tax", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("refund_due", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_profiles_id"), "tax_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_tax_profiles_user_id"), "tax_profiles", ["user_id"], unique=False)
    op.create_index(op.f("ix_tax_profiles_pan_number"), "tax_profiles", ["pan_number"], unique=False)
    op.create_index(op.f("ix_tax_profiles_assessment_year"), "tax_profiles", ["assessment_year"], unique=False)

    # -------------------------------------------------------------
    # 2. Create 'audit_logs' table for database operation tracking
    # -------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("tax_profiles")
