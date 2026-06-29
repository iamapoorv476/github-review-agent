"""add pull request unique constraint

Revision ID: bec3d16669a0
Revises: c075463eda2c
Create Date: 2026-06-29 06:59:35.772622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bec3d16669a0'
down_revision: Union[str, None] = 'c075463eda2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_pull_requests_repository_pr_number',
        'pull_requests',
        ['repository_id', 'pr_number']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_pull_requests_repository_pr_number',
        'pull_requests'
    )