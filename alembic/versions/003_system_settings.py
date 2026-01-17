"""Add system settings table.

Adds a key-value settings table for system-wide configuration
like default system prompt.

Revision ID: 003
Revises: 002
Create Date: 2026-01-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create system_settings table
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # Insert default system prompt
    op.execute(
        """
        INSERT INTO system_settings (key, value)
        VALUES (
            'default_system_prompt',
            'You are a data processing assistant. Your task is to process the input and return ONLY valid JSON output.

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no explanations, no extra text
2. Do NOT wrap the response in ```json``` code blocks
3. Do NOT include any text before or after the JSON
4. The JSON must be parseable by a machine

If the task asks for multiple values, return them as a JSON object with descriptive keys.'
        )
        """
    )


def downgrade() -> None:
    op.drop_table("system_settings")
