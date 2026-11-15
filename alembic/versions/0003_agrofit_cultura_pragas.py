"""adiciona tabela cultura_pragas (AGROFIT x EcoCrop)

Revision ID: 0003_agrofit_cultura_pragas
Revises: 0002_ecocrop_culturas_limites
Create Date: 2026-11-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_agrofit_cultura_pragas"
down_revision: Union[str, Sequence[str], None] = "0002_ecocrop_culturas_limites"
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


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "cultura_pragas" not in tables:
        op.create_table(
            "cultura_pragas",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "scientific_name",
                sa.String(),
                sa.ForeignKey("culturas_limites.scientific_name", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("cultura_agrofit", sa.String(), nullable=False),
            sa.Column("praga_nome_cientifico", sa.String(), nullable=True),
            sa.Column("praga_nome_comum", sa.Text(), nullable=True),
        )

    _ensure_index(bind, "cultura_pragas", "ix_cultura_pragas_id", ["id"])
    _ensure_index(
        bind,
        "cultura_pragas",
        "ix_cultura_pragas_scientific_name",
        ["scientific_name"],
    )
    _ensure_index(
        bind,
        "cultura_pragas",
        "ix_cultura_pragas_cultura_agrofit",
        ["cultura_agrofit"],
    )
    _ensure_index(
        bind,
        "cultura_pragas",
        "ix_cultura_pragas_praga_nome_cientifico",
        ["praga_nome_cientifico"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "cultura_pragas" in tables:
        op.drop_table("cultura_pragas")

