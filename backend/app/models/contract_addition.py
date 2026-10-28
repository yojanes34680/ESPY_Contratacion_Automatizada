"""AdicionContrato (Contract Addition) ORM Model."""
from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base

class AdicionContrato(Base):
    __tablename__ = "adiciones_contrato"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False)
    numero_adicion = Column(Integer, default=1, nullable=False)  # 1, 2, 3...
    
    # Valores económicos
    valor_adicion = Column(Float, nullable=False, default=0.0)
    valor_adicion_letras = Column(String(255), nullable=True)
    valor_anterior = Column(Float, nullable=True)
    valor_nuevo_total = Column(Float, nullable=True)
    
    # Justificación de la necesidad
    justificacion = Column(Text, nullable=True)
    
    # Disponibilidad presupuestal
    cdp_numero = Column(String(50), nullable=True)
    cdp_fecha = Column(Date, nullable=True)
    cdp_rubro = Column(String(100), nullable=True)
    cdp_rubro_nombre = Column(String(255), nullable=True)
    cdp_valor = Column(Float, nullable=True)
    
    # Representante Legal firmante (editable si persona jurídica o natural)
    contratista_nombre = Column(String(255), nullable=True)
    contratista_documento = Column(String(50), nullable=True)
    representante_legal_nombre = Column(String(255), nullable=True)
    representante_legal_documento = Column(String(50), nullable=True)
    
    # Fecha de suscripción
    fecha_adicion = Column(Date, default=date.today, nullable=False)
    
    # Referencias a archivos generados o cargados
    documento_soporte_cdp_id = Column(Integer, ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True)
    documento_minuta_id = Column(Integer, ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True)
    ruta_minuta_docx = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relación con contrato
    contrato = relationship("Contrato", back_populates="adiciones")
