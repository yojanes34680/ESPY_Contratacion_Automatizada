"""Schemas para el Agente Experto Clasificador de Códigos UNSPSC.
Estructura según las directrices oficiales y la base de datos codigos unspsc_contratacion.xlsx.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class UnspscCodeItem(BaseModel):
    codigo_unspsc: str = Field(..., description="El número de 8 dígitos extraído estrictamente del archivo oficial codigos unspsc_contratacion.xlsx")
    descripcion_codigo: str = Field(..., description="El nombre exacto del código tal cual aparece textualmente en el archivo")
    justificacion_eleccion: str = Field(..., description="Justificación obligatoria: debe citar textualmente entre comillas ('\"...\"') la actividad exacta de la propuesta económica con la que hace match. Prohibido usar frases genéricas o plantillas.")
    segmento: Optional[str] = Field(None, description="Código de 2 dígitos del Segmento")
    familia: Optional[str] = Field(None, description="Código de 4 dígitos de la Familia")
    clase: Optional[str] = Field(None, description="Código de 6 dígitos de la Clase")
    confianza: Optional[str] = Field("alta", description="Nivel de confianza: alta, media o baja")
    cita_verificada: Optional[bool] = Field(True, description="Indica si la cita textual aparece verificada en el documento")
    estado: Optional[str] = Field("aprobado", description="Estado de validación: aprobado, revisar o sugerencia_sin_validar")
    fuente_cita: Optional[str] = Field(None, description="Documento fuente de la actividad/cita: 'estudio_previo' o 'propuesta'")
    alternativas: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Códigos alternativos disponibles para cambio rápido por el usuario")

class UnspscAnalysisInput(BaseModel):
    objeto: Optional[str] = Field("", description="Descripción principal de lo que se va a contratar (opcional, se extrae del estudio previo)")
    estudio_previo: Optional[str] = Field("", description="Texto o extracto del Estudio Previo técnico, jurídico y financiero")
    propuesta_economica: Optional[str] = Field("", description="Desglose de costos, actividades o ítems de la Propuesta Económica y/o Análisis del Sector")
    contract_id: Optional[int] = Field(None, description="ID opcional del contrato del sistema para auto-completar datos y vincular")

class UnspscAnalysisResult(BaseModel):
    resumen_analisis: str = Field(..., description="Naturaleza Real del Contrato: exactamente 2 líneas definiendo el núcleo misional e ignorando la parafernalia legal")
    objeto_detectado: Optional[str] = Field(None, description="Objeto del contrato extraído automáticamente del estudio previo analizado")
    actividades_propuesta_extraidas: List[str] = Field(default_factory=list, description="Extracción y transcripción literal de al menos 3 actividades principales descritas en la Propuesta Económica")
    codigos_seleccionados: List[UnspscCodeItem] = Field(..., description="Listado de códigos UNSPSC del núcleo misional seleccionados con justificación en propuesta")
    alertas_recomendaciones: Optional[str] = Field(None, description="Alertas técnicas o de auditoría sobre ítems conexos descartados o ambigüedades")
    total_codigos: int = Field(0, description="Cantidad total de códigos seleccionados")
    fecha_analisis: Optional[str] = Field(None, description="Fecha y hora del análisis")
    motor_usado: Optional[str] = Field(None, description="Motor utilizado: 'nuevo' o 'clasico'")
    uso_ia: Optional[bool] = Field(None, description="Indica si Gemini respondió en extracción y selección (true) o si se usó respaldo (false)")

class UnspscSearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 50

class UnspscCatalogItem(BaseModel):
    codigo: str
    descripcion: str
    segmento: Optional[str] = None
    familia: Optional[str] = None
    clase: Optional[str] = None
