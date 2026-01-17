"""add error_message to web_jobs

Revision ID: 375c38d9e610
Revises: 001
Create Date: 2025-12-30 20:06:55.641540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '375c38d9e610'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add error_message column to store processing errors
    op.add_column('web_jobs', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('web_jobs', 'error_message')
