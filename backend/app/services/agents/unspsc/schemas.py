"""
Esquemas de datos internos para el pipeline del Agente UNSPSC rediseñado.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class DocumentItem(BaseModel):
    """Ítem individual extraído de la necesidad u oferta."""
    descripcion: str = Field(
        ...,
        description="Qué se compra o contrata en palabras concretas (ej. 'tapas para cajas de medidor de agua')"
    )
    naturaleza: str = Field(
        ...,
        description="bien | servicio | obra"
    )
    cita_literal: str = Field(
        ...,
        description="Frase exacta del documento donde aparece"
    )
    terminos_catalogo: List[str] = Field(
        default_factory=list,
        description="2 a 4 nombres genéricos con los que un catálogo de productos o servicios llamaría ese ítem"
    )

class DocumentExtractionResult(BaseModel):
    """Extracción estructurada del estudio previo y propuesta económica."""
    objeto: str = Field(
        ...,
        description="Texto literal del objeto del contrato"
    )
    tipo_contrato: str = Field(
        ...,
        description="suministro | obra | servicios | consultoria | mixto"
    )
    items: List[DocumentItem] = Field(
        default_factory=list,
        description="Lista de bienes, servicios u obras identificados"
    )
    uso_ia: bool = Field(
        False,
        description="Indica si la extracción fue realizada exitosamente por Gemini"
    )
