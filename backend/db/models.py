from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from backend.db.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    terrenos = relationship("Terreno", back_populates="proprietario")

class Terreno(Base):
    __tablename__ = "terrenos"
    id = Column(Integer, primary_key=True, index=True)
    nome_propriedade = Column(String)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    coordenadas_poligono = Column(JSON) # Guarda lista de dicts com lat/lng
    area_hectares = Column(Float, nullable=True)
    localizacao_central = Column(JSON, nullable=True) # Ex: {"lat": -3.73, "lng": -38.52}
    prioridades = Column(JSON) # Ex: {"agua": "escassa", "equipamento": "manual"}
    
    proprietario = relationship("Usuario", back_populates="terrenos")

class Cultura(Base):
    __tablename__ = "culturas"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    consumo_agua_mm = Column(Float)
    tempo_colheita_dias = Column(Integer)
    resistencia_pragas = Column(String, nullable=True)
    is_seed = Column(Boolean, default=False, nullable=False, index=True)
    customizada = Column(Boolean, default=True, nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)


class RotacaoProdutor(Base):
    __tablename__ = "rotacoes_produtor"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False, index=True)
    culturas = Column(JSON, nullable=False)  # Lista ordenada de culturas da rotação
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    terreno_id = Column(Integer, ForeignKey("terrenos.id"), nullable=True, index=True)
    preferencial = Column(Boolean, default=True, nullable=False, index=True)
    is_seed = Column(Boolean, default=False, nullable=False, index=True)
    beneficios = Column(String, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


RotacaoPreferencial = RotacaoProdutor


class MetricaHistoricaTerreno(Base):
    __tablename__ = "metricas_historicas_terreno"
    id = Column(Integer, primary_key=True, index=True)
    terreno_id = Column(Integer, ForeignKey("terrenos.id"), nullable=False, index=True)
    data_medicao = Column(Date, nullable=False, index=True)
    soil_moisture = Column(Float, nullable=False)
    surface_temp_c = Column(Float, nullable=False)
    precipitation_mm = Column(Float, nullable=False, default=0.0)
    is_bare_field_period = Column(Boolean, default=False, nullable=False)
    data_quality = Column(String, default="clip", nullable=False)
    origem = Column(String, default="nasa_geospatial_service", nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


FieldMetricHistory = MetricaHistoricaTerreno


class Activity(Base):
    __tablename__ = "atividades_calendario"
    id = Column(Integer, primary_key=True, index=True)
    terreno_id = Column(Integer, ForeignKey("terrenos.id"), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    cultura_id = Column(Integer, ForeignKey("culturas.id"), nullable=True, index=True)
    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True)
    tipo_atividade = Column(String, nullable=False, index=True)  # plantio, irrigacao, adubacao, manejo, colheita, inspecao
    data_programada = Column(Date, nullable=False, index=True)
    prioridade = Column(String, default="media", nullable=False)  # baixa, media, alta, critica
    status = Column(String, default="pendente", nullable=False, index=True)  # pendente, concluida
    concluida = Column(Boolean, default=False, nullable=False, index=True)
    data_conclusao = Column(DateTime, nullable=True)
    ajustada_por_alerta = Column(Boolean, default=False, nullable=False)
    motivo_ajuste = Column(String, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# Alias de retrocompatibilidade para módulos existentes
AtividadeCalendario = Activity


class AlertaClimatico(Base):
    __tablename__ = "alertas_climaticos"
    id = Column(Integer, primary_key=True, index=True)
    terreno_id = Column(Integer, ForeignKey("terrenos.id"), nullable=False, index=True)
    tipo_evento = Column(String, nullable=False, index=True)  # chuva_intensa, onda_de_calor, seca, geada, vendaval
    severidade = Column(String, default="alta", nullable=False)  # baixa, media, alta, critica
    titulo = Column(String, nullable=False)
    mensagem = Column(Text, nullable=False)
    data_evento = Column(Date, nullable=False, index=True)
    origem_gatilho = Column(String, default="ml_anomaly_detector", nullable=False)
    dados_gatilho = Column(JSON, nullable=True)
    processado_background = Column(Boolean, default=False, nullable=False)
    resumo_adaptacao = Column(Text, nullable=True)
    lido = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


Alert = AlertaClimatico


class CulturaLimite(Base):
    """Limites biológicos, térmicos, hídricos e de ciclo da base FAO EcoCrop."""

    __tablename__ = "culturas_limites"

    scientific_name = Column(String, primary_key=True, index=True)
    ecoport_code = Column(String, nullable=True, index=True)
    famname_raw = Column(String, nullable=True)
    family = Column(String, nullable=True, index=True)
    comname = Column(Text, nullable=True)
    tmin = Column(Float, nullable=True)
    tmax = Column(Float, nullable=True)
    topmn = Column(Float, nullable=True)
    topmx = Column(Float, nullable=True)
    rmin = Column(Float, nullable=True)
    rmax = Column(Float, nullable=True)
    ropmn = Column(Float, nullable=True)
    ropmx = Column(Float, nullable=True)
    gmin = Column(Integer, nullable=True)
    gmax = Column(Integer, nullable=True, index=True)
    lispa = Column(String, nullable=True)
    cat = Column(String, nullable=True, index=True)

    sinonimos = relationship(
        "CulturaSinonimo",
        back_populates="cultura",
        cascade="all, delete-orphan",
    )
    pragas = relationship(
        "CulturaPraga",
        back_populates="cultura",
        cascade="all, delete-orphan",
    )


class CulturaSinonimo(Base):
    """Nomes populares (sinônimos regionais) vinculados a uma espécie do EcoCrop."""

    __tablename__ = "culturas_sinonimos"

    id = Column(Integer, primary_key=True, index=True)
    scientific_name = Column(
        String,
        ForeignKey("culturas_limites.scientific_name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    synonym = Column(String, nullable=False, index=True)

    cultura = relationship("CulturaLimite", back_populates="sinonimos")


class CulturaPraga(Base):
    """Relação fitossanitária cultura-praga extraída do AGROFIT e cruzada com EcoCrop."""

    __tablename__ = "cultura_pragas"

    id = Column(Integer, primary_key=True, index=True)
    scientific_name = Column(
        String,
        ForeignKey("culturas_limites.scientific_name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cultura_agrofit = Column(String, nullable=False, index=True)
    praga_nome_cientifico = Column(String, nullable=True, index=True)
    praga_nome_comum = Column(Text, nullable=True)

    cultura = relationship("CulturaLimite", back_populates="pragas")
