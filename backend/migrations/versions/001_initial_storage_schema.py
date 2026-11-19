"""Create initial schema for users and tax data storage

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-10-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------
    # 1. Create 'users' table
    # -------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # -------------------------------------------------------------
    # 2. Create 'tax_records' table for data storage and retrieval
    # -------------------------------------------------------------
    op.create_table(
        "tax_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("pan_number", sa.String(length=10), nullable=False),
        sa.Column("financial_year", sa.String(length=9), nullable=False),
        sa.Column("assessment_year", sa.String(length=9), nullable=False),
        sa.Column("tax_regime", sa.String(length=10), nullable=False, server_default="new"),
        sa.Column("filing_status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("gross_total_income", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_deductions", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("taxable_income", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_tax_payable", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("computation_details", sa.Text(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_records_id"), "tax_records", ["id"], unique=False)
    op.create_index(op.f("ix_tax_records_user_id"), "tax_records", ["user_id"], unique=False)
    op.create_index(op.f("ix_tax_records_pan_number"), "tax_records", ["pan_number"], unique=False)
    op.create_index(op.f("ix_tax_records_financial_year"), "tax_records", ["financial_year"], unique=False)
    op.create_index(op.f("ix_tax_records_assessment_year"), "tax_records", ["assessment_year"], unique=False)


def downgrade() -> None:
    # Drop tax_records first due to foreign key dependency
    op.drop_index(op.f("ix_tax_records_assessment_year"), table_name="tax_records")
    op.drop_index(op.f("ix_tax_records_financial_year"), table_name="tax_records")
    op.drop_index(op.f("ix_tax_records_pan_number"), table_name="tax_records")
    op.drop_index(op.f("ix_tax_records_user_id"), table_name="tax_records")
    op.drop_index(op.f("ix_tax_records_id"), table_name="tax_records")
    op.drop_table("tax_records")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
