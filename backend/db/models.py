from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON
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
