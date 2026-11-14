from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from backend.db.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    terrenos = relationship("Terreno", back_populates="proprietario")

class Terreno(Base):
    __tablename__ = "terrenos"
    id = Column(Integer, primary_key=True, index=True)
    nome_propriedade = Column(String)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    coordenadas_poligono = Column(JSON) # Guarda lista de dicts com lat/lng
    prioridades = Column(JSON) # Ex: {"agua": "escassa", "equipamento": "manual"}
    
    proprietario = relationship("Usuario", back_populates="terrenos")

class Cultura(Base):
    __tablename__ = "culturas"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    consumo_agua_mm = Column(Float)
    tempo_colheita_dias = Column(Integer)


class AtividadeCalendario(Base):
    __tablename__ = "atividades_calendario"
    id = Column(Integer, primary_key=True, index=True)
    terreno_id = Column(Integer, ForeignKey("terrenos.id"), nullable=False, index=True)
    cultura_id = Column(Integer, ForeignKey("culturas.id"), nullable=True, index=True)
    titulo = Column(String, nullable=False)
    descricao = Column(Text, nullable=True)
    tipo_atividade = Column(String, nullable=False, index=True)  # plantio, irrigacao, adubacao, manejo, colheita, inspecao
    data_programada = Column(Date, nullable=False, index=True)
    prioridade = Column(String, default="media", nullable=False)  # baixa, media, alta, critica
    concluida = Column(Boolean, default=False, nullable=False, index=True)
    data_conclusao = Column(DateTime, nullable=True)
    ajustada_por_alerta = Column(Boolean, default=False, nullable=False)
    motivo_ajuste = Column(String, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)


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
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
