"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("github_id", sa.String(50), nullable=True),
        sa.Column("github_username", sa.String(100), nullable=True),
        sa.Column("github_access_token", sa.String(500), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("free", "pro", name="plantype"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(100), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True),
        sa.Column("scans_used_this_month", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("github_id"),
        sa.UniqueConstraint("stripe_customer_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)

    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scan_type",
            sa.Enum("github", "kubernetes", "container", "devops", "cost", "full", name="scantype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="scanstatus"),
            nullable=False,
        ),
        sa.Column("target", sa.String(500), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("issues_critical", sa.Integer(), nullable=False),
        sa.Column("issues_warning", sa.Integer(), nullable=False),
        sa.Column("issues_info", sa.Integer(), nullable=False),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_user_id", "scans", ["user_id"], unique=False)
    op.create_index("ix_scans_status", "scans", ["status"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("s3_url", sa.String(1000), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id"),
    )


def downgrade() -> None:
    op.drop_table("reports")

    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_index("ix_scans_user_id", table_name="scans")
    op.drop_table("scans")

    op.drop_index("ix_users_github_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    sa.Enum(name="scantype").drop(op.get_bind(), checkfirst=False)  # includes devops value
    sa.Enum(name="scanstatus").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="plantype").drop(op.get_bind(), checkfirst=False)
