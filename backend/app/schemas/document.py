"""Pydantic schemas for Document operations."""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.models.document import TipoDocumento, CategoriaDocumento

class DocumentoBase(BaseModel):
    contrato_id: Optional[int] = None
    contratista_id: Optional[int] = None
    tipo_documento: TipoDocumento = TipoDocumento.OTRO
    categoria: CategoriaDocumento = CategoriaDocumento.SOPORTE_CONTRATISTA

class DocumentoCreate(DocumentoBase):
    nombre_archivo_original: str
    nombre_archivo_almacenado: str
    ruta_relativa: str
    mime_type: Optional[str] = None
    tamano_bytes: int = 0
    datos_extraidos_json: Optional[Dict[str, Any]] = None

class DocumentoRead(BaseModel):
    id: int
    contrato_id: Optional[int] = None
    contratista_id: Optional[int] = None
    tipo_documento: TipoDocumento
    categoria: CategoriaDocumento
    nombre_archivo_original: str
    nombre_archivo_almacenado: str
    ruta_relativa: str
    mime_type: Optional[str] = None
    tamano_bytes: int
    datos_extraidos_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentoUploadResponse(BaseModel):
    id: int
    nombre_archivo_original: str
    tipo_documento: TipoDocumento
    categoria: CategoriaDocumento
    tamano_bytes: int
    mensaje: str
    datos_extraidos_preliminares: Optional[Dict[str, Any]] = None
