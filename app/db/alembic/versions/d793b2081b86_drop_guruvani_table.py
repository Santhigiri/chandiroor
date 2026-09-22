"""drop guruvani table

Revision ID: d793b2081b86
Revises: 0b20e68a0dea
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'd793b2081b86'
down_revision: Union[str, Sequence[str], None] = '0b20e68a0dea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_guruvani_sort_order'), table_name='guruvani')
    op.drop_table('guruvani')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('guruvani',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('text_en', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('text_ml', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_guruvani_sort_order'), 'guruvani', ['sort_order'], unique=False)
