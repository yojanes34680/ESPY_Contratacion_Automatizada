from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class APUComponenteItem(BaseModel):
    """Componente individual dentro de un APU (Material, Mano de Obra o Transporte/Equipo)."""
    descripcion: str
    unidad: str
    cantidad_rendimiento: float = 1.0
    valor_unitario: float = 0.0
    subtotal: float = 0.0

class APUDescomposicion(BaseModel):
    """Desglose técnico formal de un precio unitario en sus 3 componentes reglamentarios A, B y C."""
    componente_a_materiales: List[APUComponenteItem] = Field(default_factory=list, description="Materiales e Insumos puestos en sitio")
    subtotal_a: float = 0.0
    componente_b_mano_obra: List[APUComponenteItem] = Field(default_factory=list, description="Mano de obra y logística con factor prestacional")
    subtotal_b: float = 0.0
    componente_c_transporte_herramientas: List[APUComponenteItem] = Field(default_factory=list, description="Transporte, fletes y herramientas menores")
    subtotal_c: float = 0.0
    valor_unitario_total: float = 0.0 # Subtotal A + B + C
    ai_desglose_justificacion: Optional[str] = None

class ItemCotizacion(BaseModel):
    """Ítem cotizado por un proponente."""
    item_numero: int
    descripcion: str
    especificacion_tecnica: Optional[str] = ""
    unidad: str = "UN"
    cantidad: float = 1.0
    valor_unitario: float = 0.0
    valor_total: float = 0.0
    # Auditoría aritmética
    error_aritmetico_detectado: bool = False
    valor_total_calculado: float = 0.0
    diferencia_aritmetica: float = 0.0

class ProponenteOferta(BaseModel):
    """Oferta económica consolidada de un proponente."""
    proponente_id: str
    nombre_razon_social: str
    nit_cedula: str
    representante_legal: Optional[str] = "No especificado"
    domicilio: Optional[str] = "Municipio de Yolombó / Área de cobertura"
    telefono_correo: Optional[str] = "No suministrado"
    fecha_oferta: Optional[str] = None
    items: List[ItemCotizacion] = Field(default_factory=list)
    subtotal: float = 0.0
    iva_o_impuestos: float = 0.0
    valor_total_oferta: float = 0.0
    # Métricas y evaluación
    tiene_errores_aritmeticos: bool = False
    total_errores_aritmeticos: int = 0
    desviacion_porcentual: Optional[float] = 0.0 # Diferencia porcentual frente al menor precio
    ahorro_frente_a_este: Optional[float] = 0.0
    posicion_orden: Optional[int] = 1 # 1°, 2°, 3°
    es_seleccionado: bool = False
    observaciones_proponente: Optional[str] = ""

class ProcesoConfig(BaseModel):
    """Configuración institucional y legal del proceso de contratación y estudio de mercado conforme al Manual ESPY (PR-ESPY-002)."""
    entidad_contratante: str = "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ (ESPY S.A. E.S.P.)"
    nit_entidad: str = "811.015.112-4"
    codigo_manual_contratacion: str = "PR-ESPY-002 (Versión 02 - Resolución Nro. 5 de Junta Directiva)"
    direccion_entidad: str = "Calle Colombia 20 #20 - 74 Yolombó – Antioquia"
    contacto_entidad: str = "Celular: 3206976172 | Correo: serviciospublicosyol@hotmail.com"
    objeto_contractual: str = ""
    tipo_contrato: str = "Suministro" # Suministro, Prestación de Servicios, Obra Pública, Consultoría, etc.
    plazo_ejecucion_meses: int = 1
    smlmv_vigencia: float = 1750905.0 # Salario Mínimo Legal Mensual Vigente
    modalidad_seleccion: str = "Mínimo tres (3) cotizaciones (Entre 20 y menos de 100 SMLMV)"
    modalidad_manual_codigo: str = "ENTRE_20_Y_100_SMLMV" # AUTO, MENOR_20_SMLMV, ENTRE_20_Y_100_SMLMV, ENTRE_100_Y_1000_SMLMV, MAYOR_1000_SMLMV, DIRECTA_NUMERAL_19
    causal_directa_numeral_19: Optional[str] = None
    rango_cuantia_smlmv: str = "Entre 20 y menos de 100 SMLMV"
    presupuesto_estimado_oficial: Optional[float] = None
    anticipo_porcentaje: float = 0.0
    fecha_proceso: Optional[str] = None
    lugar_ejecucion: str = "Municipio de Yolombó, Antioquia"
    criterio_seleccion: str = "Selección objetiva del oferente con menor precio global del mercado que cumpla especificaciones técnicas"
    firmante_elaboro_nombre: str = "JOAN ALVAREZ CORREA"
    firmante_elaboro_cargo: str = "Estructurador Técnico"
    firmante_reviso_nombre: str = "Dirección Administrativa y Financiera"
    firmante_reviso_cargo: str = "Líder de Contratación"
    firmante_aprobo_nombre: str = "CAROLINA GIRALDO GÓMEZ"
    firmante_aprobo_cargo: str = "Gerente General"

class ItemAPUConsolidado(BaseModel):
    """Ítem final adjudicado con su respectivo Análisis de Precios Unitarios (APU)."""
    item_numero: int
    descripcion: str
    especificacion_tecnica: str
    unidad: str
    cantidad: float
    valor_unitario: float
    valor_total: float
    descomposicion_apu: APUDescomposicion

class EvaluacionComparativaPayload(BaseModel):
    """Payload recibido para ejecutar la evaluación comparativa y selección objetiva."""
    proceso_config: ProcesoConfig
    ofertas: List[ProponenteOferta]
    auto_desglosar_apu: bool = True
    proponente_ganador_nombre: Optional[str] = None
    custom_logo_path: Optional[str] = None

class EvaluacionComparativaResult(BaseModel):
    """Resultado final estructurado de la evaluación comparativa y APU precontractual conforme al Manual ESPY."""
    proceso_config: ProcesoConfig
    ofertas: List[ProponenteOferta]
    total_ofertas: int
    proponente_ganador: Optional[ProponenteOferta] = None
    ahorro_maximo_pesos: float = 0.0
    ahorro_maximo_porcentaje: float = 0.0
    matriz_comparativa_items: List[Dict[str, Any]] = Field(default_factory=list)
    hallazgos_evaluacion: List[str] = Field(default_factory=list)
    justificacion_seleccion: str = ""
    recomendacion_adjudicacion: str = ""
    items_apu: List[ItemAPUConsolidado] = Field(default_factory=list)
    valor_total_adjudicado: float = 0.0
    valor_total_letras: str = ""
    cuantia_smlmv_calculada: float = 0.0
    modalidad_manual_nombre: str = ""
    modalidad_manual_numeral: str = ""
    garantias_exigibles: List[Dict[str, Any]] = Field(default_factory=list)
    fecha_evaluacion: str = ""
    custom_logo_path: Optional[str] = None

