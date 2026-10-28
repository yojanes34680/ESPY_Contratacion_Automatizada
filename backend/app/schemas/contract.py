"""Pydantic schemas for Contract operations."""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.contract import TipologiaContrato, ModalidadSeleccion, EstadoContrato, UnidadPlazo
from app.schemas.contractor import ContratistaRead

class ContratoBase(BaseModel):
    numero_contrato: str
    vigencia: int = Field(default_factory=lambda: datetime.now().year)
    modalidad_seleccion: ModalidadSeleccion = ModalidadSeleccion.CONTRATACION_DIRECTA
    tipologia: TipologiaContrato = TipologiaContrato.PRESTACION_SERVICIOS
    contratista_id: int

    objeto: str
    justificacion_necesidad: Optional[str] = None
    marco_juridico: Optional[str] = None
    objetivo_general: Optional[str] = None
    objetivos_especificos: Optional[List[str]] = Field(default_factory=list)
    obligaciones_estudio_previo: Optional[List[str]] = Field(default_factory=list)
    obligaciones_minuta: Optional[List[str]] = Field(default_factory=list)
    obligaciones_empresa: Optional[List[str]] = Field(default_factory=list)

    valor_inicial: Optional[float] = None
    adicion_1: Optional[float] = 0.0
    valor_total: float = 0.0
    valor_en_letras: Optional[str] = None
    forma_pago: Optional[str] = None
    plazo_ejecucion: int = 1
    unidad_plazo: UnidadPlazo = UnidadPlazo.MESES
    plazo_texto: Optional[str] = None
    prorroga_1: Optional[str] = None
    lugar_ejecucion: Optional[str] = "Jurisdicción de la ESP"

    cdp_numero: Optional[str] = None
    cdp_fecha: Optional[date] = None
    cdp_rubro: Optional[str] = None
    rp_numero: Optional[str] = None
    rp_fecha: Optional[date] = None

    supervisor_nombre: Optional[str] = None
    supervisor_cargo: Optional[str] = None
    supervisor_tipo_documento: Optional[str] = "CC"
    supervisor_documento: Optional[str] = None
    supervisor_dependencia: Optional[str] = None

    fecha_estudio_previo: Optional[date] = None
    fecha_suscripcion: Optional[date] = None
    fecha_acta_inicio: Optional[date] = None
    fecha_terminacion: Optional[date] = None

    estado: EstadoContrato = EstadoContrato.BORRADOR
    motivo_anulacion: Optional[str] = None
    anulado_por: Optional[str] = None
    fecha_anulacion: Optional[datetime] = None
    garantias_exigidas: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadatos_agente: Optional[Dict[str, Any]] = Field(default_factory=dict)
    estudio_mercado: Optional[Dict[str, Any]] = None
    codigos_unspsc: Optional[Dict[str, Any]] = None

class ContratoAnulacionRequest(BaseModel):
    motivo: str = Field(..., min_length=15, description="Motivo detallado de la anulación (mínimo 15 caracteres)")

class ContratoCreate(ContratoBase):
    pass

class ContratoUpdate(BaseModel):
    numero_contrato: Optional[str] = None
    vigencia: Optional[int] = None
    modalidad_seleccion: Optional[ModalidadSeleccion] = None
    tipologia: Optional[TipologiaContrato] = None
    contratista_id: Optional[int] = None

    objeto: Optional[str] = None
    justificacion_necesidad: Optional[str] = None
    marco_juridico: Optional[str] = None
    objetivo_general: Optional[str] = None
    objetivos_especificos: Optional[List[str]] = None
    obligaciones_estudio_previo: Optional[List[str]] = None
    obligaciones_minuta: Optional[List[str]] = None
    obligaciones_empresa: Optional[List[str]] = None

    valor_inicial: Optional[float] = None
    adicion_1: Optional[float] = None
    valor_total: Optional[float] = None
    valor_en_letras: Optional[str] = None
    forma_pago: Optional[str] = None
    plazo_ejecucion: Optional[int] = None
    unidad_plazo: Optional[UnidadPlazo] = None
    plazo_texto: Optional[str] = None
    prorroga_1: Optional[str] = None
    lugar_ejecucion: Optional[str] = None

    cdp_numero: Optional[str] = None
    cdp_fecha: Optional[date] = None
    cdp_rubro: Optional[str] = None
    rp_numero: Optional[str] = None
    rp_fecha: Optional[date] = None

    supervisor_nombre: Optional[str] = None
    supervisor_cargo: Optional[str] = None
    supervisor_tipo_documento: Optional[str] = None
    supervisor_documento: Optional[str] = None
    supervisor_dependencia: Optional[str] = None

    fecha_estudio_previo: Optional[date] = None
    fecha_suscripcion: Optional[date] = None
    fecha_acta_inicio: Optional[date] = None
    fecha_terminacion: Optional[date] = None

    estado: Optional[EstadoContrato] = None
    garantias_exigidas: Optional[Dict[str, Any]] = None
    metadatos_agente: Optional[Dict[str, Any]] = None
    estudio_mercado: Optional[Dict[str, Any]] = None
    codigos_unspsc: Optional[Dict[str, Any]] = None

class ContratoStatusUpdate(BaseModel):
    nuevo_estado: EstadoContrato
    observacion: Optional[str] = None

class ContratoAdicionUpdate(BaseModel):
    adicion_1: float = Field(..., ge=0, description="Monto de la adición en pesos COP")
    prorroga_1: Optional[str] = None

class ContratoObjetoUpdate(BaseModel):
    objeto: str = Field(..., min_length=1, description="Nuevo objeto contractual en mayúsculas sostenidas")

class ContratoNumeroUpdate(BaseModel):
    nuevo_numero: str = Field(..., min_length=3, description="Nuevo número o código contractual (ej: CS-054-2026, CPS-050-2026)")
    forzar_prefijo: bool = Field(True, description="Si es True, asegura que el prefijo coincida con la tipología oficial (CPS/CS/CA/CO)")

class BatchRefreshNecesidadInput(BaseModel):
    desde_numero: Optional[str] = "CPS-050-2026"
    contract_ids: Optional[List[int]] = None
    actualizar_todos: bool = False

class BatchRefreshNecesidadResult(BaseModel):
    status: str
    contratos_actualizados: int
    detalles: List[Dict[str, Any]]

class ContratoRead(ContratoBase):
    id: int
    created_at: datetime
    updated_at: datetime
    contratista: Optional[ContratistaRead] = None

    model_config = ConfigDict(from_attributes=True)

class TipologiaCatalogoItem(BaseModel):
    codigo: str
    nombre: str
    descripcion: str
    enfoque_normativo: str
    agente_responsable: str

class VigenciaFiscalCreate(BaseModel):
    year: int = Field(..., ge=2000, le=2100, description="Año fiscal de la vigencia")
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    presupuesto_base: Optional[float] = 0.0
    estado: Optional[str] = "ABIERTA"
    es_vigencia_actual: Optional[bool] = True

class VigenciaFiscalRead(BaseModel):
    year: int
    nombre: str
    descripcion: Optional[str] = None
    presupuesto_base: float = 0.0
    estado: str = "ABIERTA"
    es_vigencia_actual: bool = False
    total_contratos: int = 0
    valor_total_contratado: float = 0.0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ConsecutivoSugeridoRead(BaseModel):
    sugerido: str
    consecutivo: int
    prefijo: str
    vigencia: int
