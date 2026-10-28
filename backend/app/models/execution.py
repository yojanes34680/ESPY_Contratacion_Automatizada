"""PagoContrato (Contract Payment / Expense Voucher) ORM Model."""
from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base

class PagoContrato(Base):
    __tablename__ = "pagos_contratos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Identificadores de contrato y egreso
    codigo_contrato = Column(String(50), index=True, nullable=False)
    codigo_egreso = Column(String(50), index=True, nullable=False)
    fecha_expedicion = Column(Date, nullable=True, index=True)
    nombre_beneficiario = Column(String(255), nullable=False, index=True)
    rubro_egreso = Column(String(100), nullable=True, index=True)
    
    # Valores económicos
    total_orden = Column(Float, nullable=False, default=0.0)      # Valor bruto de la orden
    total_retencion = Column(Float, nullable=False, default=0.0)  # Retenciones practicadas
    total_pagar = Column(Float, nullable=False, default=0.0)      # Valor neto girado
    total_estampillas = Column(Float, nullable=False, default=0.0) # Sumatoria de estampillas y tasas
    
    # Detalle discriminado de retenciones
    retenciones_detalle = Column(JSON, nullable=True)             # Lista estructurada [{concepto, porcentaje, valor, es_estampilla}]
    retenciones_raw = Column(Text, nullable=True)                 # Representación textual según formato TXT/CSV
    
    # Llaves foráneas a Contrato y Contratista (permiten nulo si hay contratos no estructurados)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=True, index=True)
    contratista_id = Column(Integer, ForeignKey("contratistas.id"), nullable=True, index=True)
    
    vigencia = Column(Integer, default=2026, nullable=False, index=True)
    observaciones = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relaciones
    contrato = relationship("Contrato", back_populates="pagos")
    contratista = relationship("Contratista", back_populates="pagos")
