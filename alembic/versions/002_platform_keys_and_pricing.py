"""Platform API keys and usage metering.

Adds platform-managed API keys for users without their own keys,
model pricing rate cards for billing, and extends usage tracking
with cost calculation fields.

Revision ID: 002
Revises: 375c38d9e610
Create Date: 2025-12-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "375c38d9e610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create platform_api_keys table
    op.create_table(
        "platform_api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_platform_api_keys_provider"),
        "platform_api_keys",
        ["provider"],
        unique=False,
    )

    # Create model_pricing table for rate card
    op.create_table(
        "model_pricing",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("model_pattern", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "input_cost_per_million",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
        ),
        sa.Column(
            "output_cost_per_million",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
        ),
        sa.Column(
            "markup_percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="20",
        ),
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_pricing_provider"),
        "model_pricing",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_pricing_model_pattern"),
        "model_pricing",
        ["model_pattern"],
        unique=False,
    )

    # Extend users table with platform key access control
    op.add_column(
        "users",
        sa.Column(
            "can_use_platform_key",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "monthly_usage_limit_usd",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
        ),
    )

    # Extend usage table with detailed tracking
    op.add_column(
        "usage",
        sa.Column("model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "usage",
        sa.Column("provider", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "usage",
        sa.Column(
            "used_platform_key",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "usage",
        sa.Column(
            "raw_cost_usd",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "usage",
        sa.Column(
            "markup_usd",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            server_default="0",
        ),
    )

    # Add composite index for usage queries by user and date
    op.create_index(
        "ix_usage_user_created",
        "usage",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop usage extensions
    op.drop_index("ix_usage_user_created", table_name="usage")
    op.drop_column("usage", "markup_usd")
    op.drop_column("usage", "raw_cost_usd")
    op.drop_column("usage", "used_platform_key")
    op.drop_column("usage", "provider")
    op.drop_column("usage", "model")

    # Drop users extensions
    op.drop_column("users", "monthly_usage_limit_usd")
    op.drop_column("users", "can_use_platform_key")

    # Drop model_pricing table
    op.drop_index(op.f("ix_model_pricing_model_pattern"), table_name="model_pricing")
    op.drop_index(op.f("ix_model_pricing_provider"), table_name="model_pricing")
    op.drop_table("model_pricing")

    # Drop platform_api_keys table
    op.drop_index(op.f("ix_platform_api_keys_provider"), table_name="platform_api_keys")
    op.drop_table("platform_api_keys")
