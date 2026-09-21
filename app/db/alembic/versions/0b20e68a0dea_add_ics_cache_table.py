"""add ics_cache table

Revision ID: 0b20e68a0dea
Revises: 3aa83be21d1e
Create Date: 2026-09-21 23:26:27.765219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import app.db.models.types


# revision identifiers, used by Alembic.
revision: str = '0b20e68a0dea'
down_revision: Union[str, Sequence[str], None] = '3aa83be21d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('ics_cache',
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('etag', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('updated_at', app.db.models.types.UTCDateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ics_cache')
