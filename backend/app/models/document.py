"""Documento (Document) ORM Model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base

class TipoDocumento(str, enum.Enum):
    RUT = "RUT"
    CEDULA = "CEDULA"
    CAMARA_COMERCIO = "CAMARA_COMERCIO"
    PROPUESTA = "PROPUESTA"
    ESTUDIO_MERCADO = "ESTUDIO_MERCADO"
    ANTECEDENTES = "ANTECEDENTES"
    CDP = "CDP"
    ESTUDIO_PREVIO_DOCX = "ESTUDIO_PREVIO_DOCX"
    MINUTA_DOCX = "MINUTA_DOCX"
    ACTA_INICIO_DOCX = "ACTA_INICIO_DOCX"
    ADICION_DOCX = "ADICION_DOCX"
    OTRO = "OTRO"

class CategoriaDocumento(str, enum.Enum):
    SOPORTE_CONTRATISTA = "SOPORTE_CONTRATISTA"
    GENERADO_SISTEMA = "GENERADO_SISTEMA"
    PLANTILLA = "PLANTILLA"

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id", ondelete="SET NULL"), nullable=True)
    contratista_id = Column(Integer, ForeignKey("contratistas.id", ondelete="SET NULL"), nullable=True)

    tipo_documento = Column(SQLEnum(TipoDocumento), default=TipoDocumento.OTRO, nullable=False)
    categoria = Column(
        SQLEnum(CategoriaDocumento), 
        default=CategoriaDocumento.SOPORTE_CONTRATISTA, 
        nullable=False
    )

    nombre_archivo_original = Column(String(255), nullable=False)
    nombre_archivo_almacenado = Column(String(255), nullable=False)
    ruta_relativa = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    tamano_bytes = Column(BigInteger, default=0)

    # Resultados estructurados de OCR o extracción LLM
    datos_extraidos_json = Column(JSON, default=dict, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relaciones
    contrato = relationship("Contrato", back_populates="documentos")
    contratista = relationship("Contratista", back_populates="documentos")
