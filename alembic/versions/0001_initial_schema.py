"""schema inicial com catalogo M2 e metricas historicas M6

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-14 18:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    return {col["name"] for col in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table_name)}


def _ensure_index(bind, table_name: str, index_name: str, columns: list[str], unique: bool = False) -> None:
    if index_name not in _index_names(bind, table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "usuarios" not in tables:
        op.create_table(
            "usuarios",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("nome", sa.String(), nullable=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("hashed_password", sa.String(), nullable=True),
        )
        op.create_index("ix_usuarios_id", "usuarios", ["id"], unique=False)
        op.create_index("ix_usuarios_nome", "usuarios", ["nome"], unique=False)
        op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    if "terrenos" not in tables:
        op.create_table(
            "terrenos",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("nome_propriedade", sa.String(), nullable=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("coordenadas_poligono", sa.JSON(), nullable=True),
            sa.Column("area_hectares", sa.Float(), nullable=True),
            sa.Column("localizacao_central", sa.JSON(), nullable=True),
            sa.Column("prioridades", sa.JSON(), nullable=True),
        )
        op.create_index("ix_terrenos_id", "terrenos", ["id"], unique=False)

    if "culturas" not in tables:
        op.create_table(
            "culturas",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("nome", sa.String(), nullable=True),
            sa.Column("consumo_agua_mm", sa.Float(), nullable=True),
            sa.Column("tempo_colheita_dias", sa.Integer(), nullable=True),
            sa.Column("resistencia_pragas", sa.String(), nullable=True),
            sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("customizada", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        )
        op.create_index("ix_culturas_id", "culturas", ["id"], unique=False)
        op.create_index("ix_culturas_nome", "culturas", ["nome"], unique=True)
        op.create_index("ix_culturas_is_seed", "culturas", ["is_seed"], unique=False)
        op.create_index("ix_culturas_customizada", "culturas", ["customizada"], unique=False)
        op.create_index("ix_culturas_usuario_id", "culturas", ["usuario_id"], unique=False)
    else:
        cols = _column_names(bind, "culturas")
        if "is_seed" not in cols:
            op.add_column(
                "culturas",
                sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
            _ensure_index(bind, "culturas", "ix_culturas_is_seed", ["is_seed"])
        if "customizada" not in cols:
            op.add_column(
                "culturas",
                sa.Column("customizada", sa.Boolean(), nullable=False, server_default=sa.true()),
            )
            _ensure_index(bind, "culturas", "ix_culturas_customizada", ["customizada"])
        if "usuario_id" not in cols:
            op.add_column(
                "culturas",
                sa.Column("usuario_id", sa.Integer(), nullable=True),
            )
            _ensure_index(bind, "culturas", "ix_culturas_usuario_id", ["usuario_id"])

    if "atividades_calendario" not in tables:
        op.create_table(
            "atividades_calendario",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("terreno_id", sa.Integer(), sa.ForeignKey("terrenos.id"), nullable=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("cultura_id", sa.Integer(), sa.ForeignKey("culturas.id"), nullable=True),
            sa.Column("titulo", sa.String(), nullable=False),
            sa.Column("descricao", sa.Text(), nullable=True),
            sa.Column("tipo_atividade", sa.String(), nullable=False),
            sa.Column("data_programada", sa.Date(), nullable=False),
            sa.Column("prioridade", sa.String(), nullable=False, server_default="media"),
            sa.Column("status", sa.String(), nullable=False, server_default="pendente"),
            sa.Column("concluida", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("data_conclusao", sa.DateTime(), nullable=True),
            sa.Column("ajustada_por_alerta", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("motivo_ajuste", sa.String(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_atividades_calendario_id", "atividades_calendario", ["id"], unique=False)
        op.create_index("ix_atividades_calendario_terreno_id", "atividades_calendario", ["terreno_id"], unique=False)
        op.create_index("ix_atividades_calendario_usuario_id", "atividades_calendario", ["usuario_id"], unique=False)
        op.create_index("ix_atividades_calendario_cultura_id", "atividades_calendario", ["cultura_id"], unique=False)
        op.create_index("ix_atividades_calendario_tipo_atividade", "atividades_calendario", ["tipo_atividade"], unique=False)
        op.create_index("ix_atividades_calendario_data_programada", "atividades_calendario", ["data_programada"], unique=False)
        op.create_index("ix_atividades_calendario_status", "atividades_calendario", ["status"], unique=False)
        op.create_index("ix_atividades_calendario_concluida", "atividades_calendario", ["concluida"], unique=False)

    if "alertas_climaticos" not in tables:
        op.create_table(
            "alertas_climaticos",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("terreno_id", sa.Integer(), sa.ForeignKey("terrenos.id"), nullable=False),
            sa.Column("tipo_evento", sa.String(), nullable=False),
            sa.Column("severidade", sa.String(), nullable=False, server_default="alta"),
            sa.Column("titulo", sa.String(), nullable=False),
            sa.Column("mensagem", sa.Text(), nullable=False),
            sa.Column("data_evento", sa.Date(), nullable=False),
            sa.Column("origem_gatilho", sa.String(), nullable=False, server_default="ml_anomaly_detector"),
            sa.Column("dados_gatilho", sa.JSON(), nullable=True),
            sa.Column("processado_background", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("resumo_adaptacao", sa.Text(), nullable=True),
            sa.Column("lido", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_alertas_climaticos_id", "alertas_climaticos", ["id"], unique=False)
        op.create_index("ix_alertas_climaticos_terreno_id", "alertas_climaticos", ["terreno_id"], unique=False)
        op.create_index("ix_alertas_climaticos_tipo_evento", "alertas_climaticos", ["tipo_evento"], unique=False)
        op.create_index("ix_alertas_climaticos_data_evento", "alertas_climaticos", ["data_evento"], unique=False)

    if "rotacoes_produtor" not in tables:
        op.create_table(
            "rotacoes_produtor",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("nome", sa.String(), nullable=False),
            sa.Column("culturas", sa.JSON(), nullable=False),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("terreno_id", sa.Integer(), sa.ForeignKey("terrenos.id"), nullable=True),
            sa.Column("preferencial", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("beneficios", sa.String(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_rotacoes_produtor_id", "rotacoes_produtor", ["id"], unique=False)
        op.create_index("ix_rotacoes_produtor_nome", "rotacoes_produtor", ["nome"], unique=False)
        op.create_index("ix_rotacoes_produtor_usuario_id", "rotacoes_produtor", ["usuario_id"], unique=False)
        op.create_index("ix_rotacoes_produtor_terreno_id", "rotacoes_produtor", ["terreno_id"], unique=False)
        op.create_index("ix_rotacoes_produtor_preferencial", "rotacoes_produtor", ["preferencial"], unique=False)
        op.create_index("ix_rotacoes_produtor_is_seed", "rotacoes_produtor", ["is_seed"], unique=False)

    if "metricas_historicas_terreno" not in tables:
        op.create_table(
            "metricas_historicas_terreno",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("terreno_id", sa.Integer(), sa.ForeignKey("terrenos.id"), nullable=False),
            sa.Column("data_medicao", sa.Date(), nullable=False),
            sa.Column("soil_moisture", sa.Float(), nullable=False),
            sa.Column("surface_temp_c", sa.Float(), nullable=False),
            sa.Column("precipitation_mm", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("is_bare_field_period", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("data_quality", sa.String(), nullable=False, server_default="clip"),
            sa.Column("origem", sa.String(), nullable=False, server_default="nasa_geospatial_service"),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_metricas_historicas_terreno_id", "metricas_historicas_terreno", ["id"], unique=False)
        op.create_index("ix_metricas_historicas_terreno_terreno_id", "metricas_historicas_terreno", ["terreno_id"], unique=False)
        op.create_index("ix_metricas_historicas_terreno_data_medicao", "metricas_historicas_terreno", ["data_medicao"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    for table_name in (
        "metricas_historicas_terreno",
        "rotacoes_produtor",
        "alertas_climaticos",
        "atividades_calendario",
        "culturas",
        "terrenos",
        "usuarios",
    ):
        if table_name in tables:
            op.drop_table(table_name)
