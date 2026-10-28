"""Vigencia Fiscal (Fiscal Year / Contracting Era) ORM Model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime

from app.database import Base

class VigenciaFiscal(Base):
    __tablename__ = "vigencias_fiscales"

    year = Column(Integer, primary_key=True, index=True)  # Ej: 2026, 2027, 2028
    nombre = Column(String(100), nullable=False)          # Ej: "Vigencia Fiscal 2026"
    descripcion = Column(Text, nullable=True)             # Justificación o decreto presupuestal
    presupuesto_base = Column(Float, default=0.0)         # Presupuesto estimado en COP
    estado = Column(String(50), default="ABIERTA")        # ABIERTA, CERRADA, PLANIFICACION
    es_vigencia_actual = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
