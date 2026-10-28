"""Modelo de datos para el Catálogo Oficial de Códigos UNSPSC.
Basado estrictamente en codigos unspsc_contratacion.xlsx (52.845 registros oficiales).
"""
from sqlalchemy import Column, String, Text, Index
from app.database import Base

class UnspscItem(Base):
    __tablename__ = "unspsc_catalog"

    codigo = Column(String(10), primary_key=True, index=True)
    descripcion = Column(String(500), nullable=False)
    segmento = Column(String(2), index=True, nullable=True)
    familia = Column(String(4), index=True, nullable=True)
    clase = Column(String(6), index=True, nullable=True)

    __table_args__ = (
        Index("idx_unspsc_segmento_familia", "segmento", "familia"),
    )

class UnspscHistoricalFeedback(Base):
    """
    Historial de pares (ítem, código_aprobado) confirmados por el usuario o supervisor.
    Alimenta automáticamente la búsqueda de candidatos para contratos futuros sin reglas ad-hoc.
    """
    __tablename__ = "unspsc_historical_feedback"

    id = Column(String(50), primary_key=True)
    item_descripcion = Column(String(500), nullable=False, index=True)
    codigo_unspsc = Column(String(10), nullable=False, index=True)
    objeto_contrato = Column(Text, nullable=True)
    contract_id = Column(String(50), nullable=True)
    creado_en = Column(String(30), nullable=True)
