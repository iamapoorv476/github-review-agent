"""add installation api key

Revision ID: a41f2e9d77c1
Revises: bec3d16669a0
Create Date: 2026-08-04

Per-installation API key for MCP / external read access.
hash → sha256 hex for auth lookup; encrypted → Fernet, re-displayable
on the dashboard "Connect Claude" page.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a41f2e9d77c1'
down_revision: Union[str, None] = 'bec3d16669a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'installations',
        sa.Column('api_key_hash', sa.Text(), nullable=True)
    )
    op.add_column(
        'installations',
        sa.Column('api_key_encrypted', sa.Text(), nullable=True)
    )
    op.create_index(
        'ix_installations_api_key_hash',
        'installations',
        ['api_key_hash'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_installations_api_key_hash', table_name='installations')
    op.drop_column('installations', 'api_key_encrypted')
    op.drop_column('installations', 'api_key_hash')