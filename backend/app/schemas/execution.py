"""Schemas for Contract Execution and Payment Vouchers."""
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class RetencionItem(BaseModel):
    concepto: str
    porcentaje: float = 0.0
    valor: float = 0.0
    es_estampilla: bool = False

class RetencionConceptoSummary(BaseModel):
    concepto: str
    total_retenido: float
    porcentaje_del_total: float
    conteo_pagos: int
    es_estampilla: bool = False

class PagoContratoBase(BaseModel):
    codigo_contrato: str
    codigo_egreso: str
    fecha_expedicion: Optional[date] = None
    nombre_beneficiario: str
    rubro_egreso: Optional[str] = None
    total_orden: float = Field(default=0.0, description="Valor bruto de la orden")
    total_retencion: float = Field(default=0.0, description="Total de retenciones aplicadas")
    total_pagar: float = Field(default=0.0, description="Total neto a pagar")
    total_estampillas: float = Field(default=0.0, description="Total de estampillas y tasas aplicadas")
    retenciones_detalle: Optional[List[RetencionItem]] = None
    retenciones_raw: Optional[str] = None
    vigencia: int = 2026
    observaciones: Optional[str] = None

class PagoContratoCreate(PagoContratoBase):
    contrato_id: Optional[int] = None
    contratista_id: Optional[int] = None

class PagoContratoUpdate(BaseModel):
    codigo_contrato: Optional[str] = None
    codigo_egreso: Optional[str] = None
    fecha_expedicion: Optional[date] = None
    nombre_beneficiario: Optional[str] = None
    rubro_egreso: Optional[str] = None
    total_orden: Optional[float] = None
    total_retencion: Optional[float] = None
    total_pagar: Optional[float] = None
    total_estampillas: Optional[float] = None
    retenciones_detalle: Optional[List[RetencionItem]] = None
    retenciones_raw: Optional[str] = None
    observaciones: Optional[str] = None

class PagoContratoReassign(BaseModel):
    contrato_id: Optional[int] = None
    codigo_contrato: Optional[str] = None
    observaciones: Optional[str] = None

class PagoContratoResponse(PagoContratoBase):
    id: int
    contrato_id: Optional[int] = None
    contratista_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class PagoContratoDetailResponse(PagoContratoResponse):
    contratista_documento: Optional[str] = None
    contratista_tipo_documento: Optional[str] = None
    contratista_banco: Optional[str] = None
    contratista_tipo_cuenta: Optional[str] = None
    contratista_numero_cuenta: Optional[str] = None
    contrato_objeto: Optional[str] = None
    contrato_valor_total: Optional[float] = None

class ContratoEjecucionSummary(BaseModel):
    id: int
    numero_contrato: str
    tipologia: str
    contratista_id: int
    contratista_nombre: str
    valor_total: float
    valor_inicial: float = 0.0
    adicion_1: float = 0.0
    estado: str
    total_ejecutado: float
    total_retenciones: float
    total_estampillas: float = 0.0
    total_neto_pagado: float
    saldo_por_ejecutar: float
    porcentaje_ejecucion: float
    conteo_pagos: int

class ContratistaEjecucionSummary(BaseModel):
    id: int
    nombre_o_razon_social: str
    numero_documento: str
    tipo_documento: str
    tipo_persona: str
    banco_nombre: Optional[str] = None
    banco_tipo_cuenta: Optional[str] = None
    banco_numero_cuenta: Optional[str] = None
    total_contratos: int
    valor_total_contratado: float
    total_ejecutado: float
    total_retenciones: float
    total_estampillas: float = 0.0
    total_neto_pagado: float
    saldo_por_ejecutar: float
    porcentaje_ejecucion: float
    conteo_pagos: int
    contratos: List[ContratoEjecucionSummary] = []
    pagos: List[PagoContratoResponse] = []

class RubroEjecucionItem(BaseModel):
    rubro: str
    total_ejecutado: float
    total_neto: float
    conteo_pagos: int
    porcentaje_del_total: float

class MesEjecucionItem(BaseModel):
    mes_key: str
    mes_nombre: str
    total_ejecutado: float
    total_retencion: float
    total_neto: float
    conteo_pagos: int

class ResumenEjecucionGlobal(BaseModel):
    vigencia: Optional[str] = "2026"
    total_contratos: int
    total_contratos_con_pagos: int
    total_contratistas: int
    total_contratado: float
    total_ejecutado: float
    total_retenciones: float
    total_estampillas: float = 0.0
    total_neto_pagado: float
    saldo_por_ejecutar: float
    porcentaje_ejecucion_global: float
    conteo_comprobantes: int
    rubros: List[RubroEjecucionItem] = []
    meses: List[MesEjecucionItem] = []
    top_contratistas: List[ContratistaEjecucionSummary] = []
    retenciones_breakdown: List[RetencionConceptoSummary] = []
