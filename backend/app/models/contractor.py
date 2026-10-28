"""Contratista (Contractor) ORM Model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base

class TipoPersona(str, enum.Enum):
    NATURAL = "NATURAL"
    JURIDICA = "JURIDICA"

class TipoDocumento(str, enum.Enum):
    CC = "CC"
    NIT = "NIT"
    CE = "CE"
    PASAPORTE = "PASAPORTE"

class RegimenTributario(str, enum.Enum):
    RESPONSABLE_IVA = "RESPONSABLE_IVA"
    NO_RESPONSABLE_IVA = "NO_RESPONSABLE_IVA"
    GRAN_CONTRIBUYENTE = "GRAN_CONTRIBUYENTE"
    REGIMEN_SIMPLE = "REGIMEN_SIMPLE"

class Contratista(Base):
    __tablename__ = "contratistas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tipo_persona = Column(SQLEnum(TipoPersona), default=TipoPersona.NATURAL, nullable=False)
    tipo_documento = Column(SQLEnum(TipoDocumento), default=TipoDocumento.CC, nullable=False)
    numero_documento = Column(String(50), unique=True, index=True, nullable=False)
    digito_verificacion = Column(String(5), nullable=True)
    nombre_o_razon_social = Column(String(255), nullable=False, index=True)
    nombre_comercial = Column(String(255), nullable=True)
    
    # Representación legal (para personas jurídicas)
    representante_legal_nombre = Column(String(255), nullable=True)
    representante_legal_documento = Column(String(50), nullable=True)
    
    # Ubicación y contacto
    direccion = Column(String(255), nullable=True)
    municipio = Column(String(100), default="Bogotá D.C.", nullable=True)
    departamento = Column(String(100), default="Cundinamarca", nullable=True)
    correo_electronico = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    
    # Información fiscal y bancaria
    regimen_tributario = Column(
        SQLEnum(RegimenTributario), 
        default=RegimenTributario.NO_RESPONSABLE_IVA, 
        nullable=True
    )
    banco_nombre = Column(String(100), nullable=True)
    banco_tipo_cuenta = Column(String(50), nullable=True)  # Ahorros / Corriente
    banco_numero_cuenta = Column(String(50), nullable=True)
    
    # Estado activo / inactivo
    activo = Column(Boolean, default=True, nullable=False)

    # Perfil / Capacidad
    perfil_o_experiencia_resumen = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relaciones (sin delete-orphan para contratos)
    contratos = relationship("Contrato", back_populates="contratista")
    documentos = relationship("Documento", back_populates="contratista", foreign_keys="Documento.contratista_id")
    pagos = relationship("PagoContrato", back_populates="contratista")


    @property
    def codigos_contratos(self) -> list:
        """Lista de números o códigos de contratos celebrados por este contratista."""
        if not self.contratos:
            return []
        return [c.numero_contrato for c in self.contratos if c.numero_contrato]
