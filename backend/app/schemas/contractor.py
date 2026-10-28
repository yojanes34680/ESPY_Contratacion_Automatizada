"""Pydantic schemas for Contractor operations."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.contractor import TipoPersona, TipoDocumento, RegimenTributario

class ContratistaBase(BaseModel):
    tipo_persona: TipoPersona = TipoPersona.NATURAL
    tipo_documento: TipoDocumento = TipoDocumento.CC
    numero_documento: str
    digito_verificacion: Optional[str] = None
    nombre_o_razon_social: str
    nombre_comercial: Optional[str] = None
    representante_legal_nombre: Optional[str] = None
    representante_legal_documento: Optional[str] = None
    direccion: Optional[str] = None
    municipio: Optional[str] = "Bogotá D.C."
    departamento: Optional[str] = "Cundinamarca"
    correo_electronico: Optional[str] = None
    telefono: Optional[str] = None
    regimen_tributario: Optional[RegimenTributario] = RegimenTributario.NO_RESPONSABLE_IVA
    banco_nombre: Optional[str] = None
    banco_tipo_cuenta: Optional[str] = None
    banco_numero_cuenta: Optional[str] = None
    perfil_o_experiencia_resumen: Optional[str] = None
    activo: bool = True

class ContratistaCreate(ContratistaBase):
    pass

class ContratistaUpdate(BaseModel):
    tipo_persona: Optional[TipoPersona] = None
    tipo_documento: Optional[TipoDocumento] = None
    numero_documento: Optional[str] = None
    digito_verificacion: Optional[str] = None
    nombre_o_razon_social: Optional[str] = None
    nombre_comercial: Optional[str] = None
    representante_legal_nombre: Optional[str] = None
    representante_legal_documento: Optional[str] = None
    direccion: Optional[str] = None
    municipio: Optional[str] = None
    departamento: Optional[str] = None
    correo_electronico: Optional[str] = None
    telefono: Optional[str] = None
    regimen_tributario: Optional[RegimenTributario] = None
    banco_nombre: Optional[str] = None
    banco_tipo_cuenta: Optional[str] = None
    banco_numero_cuenta: Optional[str] = None
    perfil_o_experiencia_resumen: Optional[str] = None
    activo: Optional[bool] = None

class ContratoSummary(BaseModel):
    id: int
    numero_contrato: str
    vigencia: int
    tipologia: str
    valor_total: float
    estado: str
    objeto: Optional[str] = None
    supervisor_nombre: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class DocumentoSummary(BaseModel):
    id: int
    tipo_documento: str
    nombre_archivo_original: str
    tamano_bytes: Optional[int] = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ContratistaRead(ContratistaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    contratos: list[ContratoSummary] = []
    codigos_contratos: list[str] = []
    documentos: list[DocumentoSummary] = []

    model_config = ConfigDict(from_attributes=True)
