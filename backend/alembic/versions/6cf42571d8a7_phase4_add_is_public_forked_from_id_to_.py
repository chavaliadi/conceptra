"""phase4_add_is_public_forked_from_id_to_plans

Revision ID: 6cf42571d8a7
Revises: 9f370f468b06
Create Date: 2026-06-25 14:22:45.150020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6cf42571d8a7'
down_revision: Union[str, Sequence[str], None] = '9f370f468b06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_public as nullable first so existing rows don't violate NOT NULL
    op.add_column('plans', sa.Column('is_public', sa.Boolean(), nullable=True))
    # Backfill existing rows with False (private) before enforcing NOT NULL
    op.execute("UPDATE plans SET is_public = FALSE WHERE is_public IS NULL")
    op.alter_column('plans', 'is_public', nullable=False)

    op.add_column('plans', sa.Column('forked_from_id', sa.UUID(), nullable=True))
    op.create_index('idx_plans_is_public', 'plans', ['is_public'], unique=False)
    op.create_foreign_key(
        'fk_plans_forked_from_id', 'plans', 'plans',
        ['forked_from_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_plans_forked_from_id', 'plans', type_='foreignkey')
    op.drop_index('idx_plans_is_public', table_name='plans')
    op.drop_column('plans', 'forked_from_id')
    op.drop_column('plans', 'is_public')
