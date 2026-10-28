"""Auditoría (Audit Log) ORM Model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

class Auditoria(Base):
    __tablename__ = "auditoria"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id", ondelete="SET NULL"), nullable=True)
    accion = Column(String(100), nullable=False)  # CREACION, SUBIDA_DOC, AGENTE_LLM, GEN_DOCX, SYNC_EXCEL, ANULACION
    detalle = Column(Text, nullable=True)
    usuario = Column(String(100), default="Sistema", nullable=False)
    usuario_documento = Column(String(50), nullable=True)
    usuario_nombre = Column(String(200), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    contrato = relationship("Contrato", back_populates="auditorias")
