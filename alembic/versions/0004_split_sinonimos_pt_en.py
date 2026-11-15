"""separa culturas_sinonimos em culturas_sinonimos_pt e culturas_sinonimos_en

Revision ID: 0004_split_sinonimos_pt_en
Revises: 0003_agrofit_cultura_pragas
Create Date: 2026-11-15 11:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_split_sinonimos_pt_en"
down_revision: Union[str, Sequence[str], None] = "0003_agrofit_cultura_pragas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _index_names(bind, table_name: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table_name)}


def _ensure_index(
    bind, table_name: str, index_name: str, columns: list[str], unique: bool = False
) -> None:
    if index_name not in _index_names(bind, table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _create_synonym_table(bind, tables: set[str], table_name: str) -> None:
    if table_name not in tables:
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "scientific_name",
                sa.String(),
                sa.ForeignKey("culturas_limites.scientific_name", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("synonym", sa.String(), nullable=False),
        )

    _ensure_index(bind, table_name, f"ix_{table_name}_id", ["id"])
    _ensure_index(
        bind, table_name, f"ix_{table_name}_scientific_name", ["scientific_name"]
    )
    _ensure_index(bind, table_name, f"ix_{table_name}_synonym", ["synonym"])


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    _create_synonym_table(bind, tables, "culturas_sinonimos_pt")
    _create_synonym_table(bind, tables, "culturas_sinonimos_en")

    if "culturas_sinonimos" in tables:
        op.drop_table("culturas_sinonimos")


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    _create_synonym_table(bind, tables, "culturas_sinonimos")

    if "culturas_sinonimos_en" in tables:
        op.drop_table("culturas_sinonimos_en")
    if "culturas_sinonimos_pt" in tables:
        op.drop_table("culturas_sinonimos_pt")

