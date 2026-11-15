"""adiciona tabelas culturas_limites e culturas_sinonimos (EcoCrop)

Revision ID: 0002_ecocrop_culturas_limites
Revises: 0001_initial_schema
Create Date: 2026-11-15 10:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_ecocrop_culturas_limites"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
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

    if "culturas_limites" not in tables:
        op.create_table(
            "culturas_limites",
            sa.Column("scientific_name", sa.String(), primary_key=True, nullable=False),
            sa.Column("ecoport_code", sa.String(), nullable=True),
            sa.Column("famname_raw", sa.String(), nullable=True),
            sa.Column("family", sa.String(), nullable=True),
            sa.Column("comname", sa.Text(), nullable=True),
            sa.Column("tmin", sa.Float(), nullable=True),
            sa.Column("tmax", sa.Float(), nullable=True),
            sa.Column("topmn", sa.Float(), nullable=True),
            sa.Column("topmx", sa.Float(), nullable=True),
            sa.Column("rmin", sa.Float(), nullable=True),
            sa.Column("rmax", sa.Float(), nullable=True),
            sa.Column("ropmn", sa.Float(), nullable=True),
            sa.Column("ropmx", sa.Float(), nullable=True),
            sa.Column("gmin", sa.Integer(), nullable=True),
            sa.Column("gmax", sa.Integer(), nullable=True),
            sa.Column("lispa", sa.String(), nullable=True),
            sa.Column("cat", sa.String(), nullable=True),
        )

    _ensure_index(
        bind,
        "culturas_limites",
        "ix_culturas_limites_scientific_name",
        ["scientific_name"],
    )
    _ensure_index(
        bind, "culturas_limites", "ix_culturas_limites_ecoport_code", ["ecoport_code"]
    )
    _ensure_index(bind, "culturas_limites", "ix_culturas_limites_family", ["family"])
    _ensure_index(bind, "culturas_limites", "ix_culturas_limites_gmax", ["gmax"])
    _ensure_index(bind, "culturas_limites", "ix_culturas_limites_cat", ["cat"])

    if "culturas_sinonimos" not in tables:
        op.create_table(
            "culturas_sinonimos",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "scientific_name",
                sa.String(),
                sa.ForeignKey("culturas_limites.scientific_name", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("synonym", sa.String(), nullable=False),
        )

    _ensure_index(bind, "culturas_sinonimos", "ix_culturas_sinonimos_id", ["id"])
    _ensure_index(
        bind,
        "culturas_sinonimos",
        "ix_culturas_sinonimos_scientific_name",
        ["scientific_name"],
    )
    _ensure_index(
        bind, "culturas_sinonimos", "ix_culturas_sinonimos_synonym", ["synonym"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "culturas_sinonimos" in tables:
        op.drop_table("culturas_sinonimos")
    if "culturas_limites" in tables:
        op.drop_table("culturas_limites")

