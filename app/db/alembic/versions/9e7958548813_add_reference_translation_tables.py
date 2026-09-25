"""add reference translation tables (v2, additive)

Revision ID: 9e7958548813
Revises: d793b2081b86
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '9e7958548813'
down_revision: Union[str, Sequence[str], None] = 'd793b2081b86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (translation table, FK column, parent table)
_TABLES = [
    ('thithi_translation', 'thithi_id', 'thithi'),
    ('nakshatra_translation', 'nakshatra_id', 'nakshatra'),
    ('paksha_translation', 'paksha_id', 'paksha'),
    ('malayalam_masa_translation', 'malayalam_masa_id', 'malayalam_masa'),
    ('chandra_masa_translation', 'chandra_masa_id', 'chandra_masa'),
]


def upgrade() -> None:
    """Upgrade schema.

    Adds one row-per-(parent, language_code) translation table per reference
    lookup table (thithi/nakshatra/paksha/malayalam_masa/chandra_masa),
    matching kumily's translation-table pattern (the direct precedent is
    kumily's migration 9363bde18594, which normalized guruvani's
    text_en/text_ml into guruvani_translation). Existing ml/en values are
    backfilled into 'en'/'ml' translation rows.

    Unlike kumily's guruvani migration, this does NOT drop the ml/en
    columns on the parent tables — chandiroor's v1
    /api/v1/panchangam/thithi|nakshatra|masa|chandra-masa endpoints still
    read those columns directly via
    db/reference_repository.py::ReferenceRepository.list_*() and must keep
    working unchanged. The new *_translation tables are purely additive,
    backing the new /api/v2/panchangam/... endpoints instead.

    ml/en are nullable on every parent table and are NULL in every current
    test/dev database (db/seed.py only seeds structural columns) — the
    `WHERE en IS NOT NULL` / `WHERE ml IS NOT NULL` guards below make the
    backfill a no-op there, while still backfilling real data on a database
    seeded from db/sql/02_seed.sql (where ml/en are populated literals).
    """
    for table, fk_column, parent in _TABLES:
        uq_name = f"uq_{table}_{fk_column.removesuffix('_id')}_language"
        op.create_table(
            table,
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column(fk_column, sa.Integer(), nullable=False),
            sa.Column('language_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column('text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.ForeignKeyConstraint([fk_column], [f'{parent}.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(fk_column, 'language_code', name=uq_name),
        )
        op.create_index(op.f(f'ix_{table}_{fk_column}'), table, [fk_column], unique=False)
        op.create_index(op.f(f'ix_{table}_language_code'), table, ['language_code'], unique=False)

        op.execute(
            f"INSERT INTO {table} ({fk_column}, language_code, text) "
            f"SELECT id, 'en', en FROM {parent} WHERE en IS NOT NULL"
        )
        op.execute(
            f"INSERT INTO {table} ({fk_column}, language_code, text) "
            f"SELECT id, 'ml', ml FROM {parent} WHERE ml IS NOT NULL"
        )


def downgrade() -> None:
    """Downgrade schema.

    Drops the five translation tables. No column restore is needed — ml/en
    were never dropped by upgrade().
    """
    for table, fk_column, _parent in reversed(_TABLES):
        op.drop_index(op.f(f'ix_{table}_language_code'), table_name=table)
        op.drop_index(op.f(f'ix_{table}_{fk_column}'), table_name=table)
        op.drop_table(table)
