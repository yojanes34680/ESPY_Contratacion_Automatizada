"""Pydantic schemas for AI Extraction and Multi-Agent Generation."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ContratistaExtractedData(BaseModel):
    """Structured extraction schema for contractor documents (RUT, Cédula, Propuesta)."""
    tipo_persona: Optional[str] = Field(None, description="NATURAL o JURIDICA")
    tipo_documento: Optional[str] = Field(None, description="CC, NIT, CE")
    numero_documento: Optional[str] = Field(None, description="Número de documento o NIT sin dígito")
    digito_verificacion: Optional[str] = Field(None, description="Dígito de verificación para NIT")
    nombre_o_razon_social: Optional[str] = Field(None, description="Nombre completo o Razón Social exacta")
    nombre_comercial: Optional[str] = Field(None, description="Nombre comercial si aplica")
    representante_legal_nombre: Optional[str] = Field(None, description="Nombre del representante legal")
    representante_legal_documento: Optional[str] = Field(None, description="Documento del representante legal")
    direccion: Optional[str] = Field(None, description="Dirección fiscal o de contacto")
    municipio: Optional[str] = Field(None, description="Municipio / Ciudad")
    departamento: Optional[str] = Field(None, description="Departamento")
    correo_electronico: Optional[str] = Field(None, description="Correo electrónico oficial")
    telefono: Optional[str] = Field(None, description="Teléfono de contacto")
    regimen_tributario: Optional[str] = Field(None, description="RESPONSABLE_IVA o NO_RESPONSABLE_IVA")
    actividad_economica_ciiu: Optional[str] = Field(None, description="Código y descripción CIIU principal")
    valor_propuesto: Optional[float] = Field(None, description="Valor económico de la propuesta en COP")
    plazo_propuesto: Optional[int] = Field(None, description="Plazo de ejecución propuesto")
    unidad_plazo_propuesto: Optional[str] = Field(None, description="MESES o DIAS")
    perfil_profesional_resumen: Optional[str] = Field(None, description="Síntesis de experiencia y perfil")
    banco_nombre: Optional[str] = Field(None, description="Entidad bancaria del contratista")
    banco_tipo_cuenta: Optional[str] = Field(None, description="Ahorros o Corriente")
    banco_numero_cuenta: Optional[str] = Field(None, description="Número de cuenta bancaria")
    forma_pago_propuesta: Optional[str] = Field(None, description="Condiciones o forma de pago ofertada")
    objeto_propuesto: Optional[str] = Field(None, description="Objeto ofertado en la propuesta")
    alcance_propuesto: Optional[str] = Field(None, description="Alcance o especificaciones técnicas de la propuesta")
    actividades_propuesta: Optional[List[str]] = Field(default_factory=list, description="Lista desglosada de actividades u objetivos específicos de la propuesta, iniciando obligatoriamente con verbo rector en infinitivo")
    objetivo_general: Optional[str] = Field(None, description="Objetivo general formulado o extraído de la propuesta con verbo en infinitivo")
    objetivos_especificos: Optional[List[str]] = Field(default_factory=list, description="Objetivos específicos medibles derivados de la propuesta; cada objetivo DEBE iniciar obligatoriamente con un verbo de acción en infinitivo (ej: Realizar, Ejecutar, Suministrar, Instalar)")
    
    # Datos de Disponibilidad Presupuestal (CDP) si aplica
    cdp_numero: Optional[str] = Field(None, description="Número consecutivo del CDP")
    cdp_fecha: Optional[str] = Field(None, description="Fecha de expedición del CDP (YYYY-MM-DD)")
    cdp_rubro: Optional[str] = Field(None, description="Código del rubro presupuestal")
    cdp_rubro_nombre: Optional[str] = Field(None, description="Nombre o descripción del rubro presupuestal")
    cdp_valor: Optional[float] = Field(None, description="Valor del rubro o saldo disponible en el CDP")
    cdp_objeto: Optional[str] = Field(None, description="Objeto de la disponibilidad presupuestal en el CDP")
    cdp_clasificadores: Optional[List[str]] = Field(default_factory=list, description="Clasificadores presupuestales CCPET del CDP")
    cdp_texto_completo: Optional[str] = Field(None, description="Texto legal consolidado del CDP con clasificadores y valor")

    subdocumentos_detectados: Optional[List[str]] = Field(default_factory=list, description="Tipos de documentos identificados en el archivo")

class ContractDraftingInput(BaseModel):
    """Input payload to trigger contract drafting by specialized agents."""
    contrato_id: Optional[int] = None
    tipologia: str = Field(..., description="PRESTACION_SERVICIOS, OBRA, SUMINISTRO")
    modalidad: Optional[str] = "CONTRATACION_DIRECTA"
    necesidad_descripcion: Optional[str] = Field(default="", description="Descripción resumida del requerimiento de la ESP")
    alcance_esperado: Optional[str] = Field(None, description="Alcance o especificaciones deseadas")
    valor_estimado: Optional[float] = 0.0
    plazo: Optional[int] = 1
    unidad_plazo: Optional[str] = "MESES"
    contratista_id: Optional[int] = None
    datos_contratista_contexto: Optional[Dict[str, Any]] = None
    document_ids: Optional[List[int]] = Field(default_factory=list, description="IDs de documentos soporte cargados")
    nivel_extension: Optional[str] = Field(default="MEDIA", description="Nivel de extensión: CORTA, MEDIA, COMPLETA")
    instrucciones_adicionales: Optional[str] = Field(None, description="Instrucciones específicas del usuario para el agente")
    propuesta_items: Optional[List[Any]] = Field(None, description="Ítems extraídos de la propuesta económica")
    propuesta_texto: Optional[str] = Field(None, description="Texto completo extraído de la propuesta o cotización")

class ContractDraftingResult(BaseModel):
    """Output schema produced by the specialized contract drafting agents."""
    tipologia: str
    agente_nombre: str
    objeto: str = Field(..., description="Objeto contractual técnico y normativo")
    justificacion_necesidad: str = Field(..., description="Justificación fundamentada en Ley 142/1994 y necesidad de la ESP")
    objetivo_general: str = Field(..., description="Objetivo general claro y medible iniciado con verbo en infinitivo")
    objetivos_especificos: List[str] = Field(default_factory=list, description="Lista de objetivos específicos técnicos; cada uno DEBE iniciar obligatoriamente con un verbo rector en infinitivo (ej: Realizar, Ejecutar, Suministrar, Instalar, etc.)")
    obligaciones_estudio_previo: List[str] = Field(
        default_factory=list, 
        description="Obligaciones técnicas del contratista para el Estudio Previo"
    )
    obligaciones_minuta: List[str] = Field(
        default_factory=list, 
        description="Obligaciones jurídicas y operativas del contratista para la Minuta del Contrato"
    )
    obligaciones_empresa: List[str] = Field(
        default_factory=list,
        description="Obligaciones jurídicas y operativas de LA EMPRESA (ESPY S.A. E.S.P.) adaptadas estrictamente de acuerdo a la tipología del contrato celebrado (Prestación de Servicios, Suministro, Obra, Arrendamiento, etc.) para la Minuta del Contrato"
    )
    garantias_sugeridas: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Amparos sugeridos (cumplimiento, salarios, calidad/estabilidad, etc.) con % y vigencias"
    )
    clausulas_especiales: List[str] = Field(
        default_factory=list, 
        description="Cláusulas específicas (no subordinación para servicios, SST para obra, entregas bodega para suministro)"
    )
    marco_juridico: Optional[str] = Field(
        None, 
        description="Marco jurídico y fundamentación legal especializada por tipología (Ley 142/1994, Código Civil, Código de Comercio y normas técnicas)"
    )
    observaciones_juridicas: Optional[str] = Field(None, description="Recomendaciones jurídicas para el área de contratación")

class JustificacionGenerationInput(BaseModel):
    """Solicitud para la elaboración automática de la Justificación del Estudio Previo."""
    document_ids: List[int] = Field(default_factory=list, description="IDs de los documentos en BD. Es obligatorio que incluya Estudio de Mercado o Propuesta.")
    tipologia: str = Field(default="PRESTACION_SERVICIOS", description="PRESTACION_SERVICIOS, OBRA, SUMINISTRO")
    modalidad: Optional[str] = "CONTRATACION_DIRECTA"
    objeto: Optional[str] = Field(None, description="Objeto del contrato formulado o en estructuración")
    necesidad_contexto: Optional[str] = Field(None, description="Detalle contextual o necesidad operativa de la ESP")
    contratista_nombre: Optional[str] = Field(None, description="Nombre o razón social del contratista")
    valor_estimado: Optional[float] = Field(None, description="Presupuesto oficial o cotizado en COP")
    nivel_extension: Optional[str] = Field(default="MEDIA", description="Nivel de extensión: CORTA, MEDIA, COMPLETA")
    instrucciones_adicionales: Optional[str] = Field(None, description="Instrucciones específicas adicionales")
    propuesta_items: Optional[List[Any]] = Field(None, description="Ítems extraídos de la propuesta")
    propuesta_texto: Optional[str] = Field(None, description="Texto de la propuesta económica")


class JustificacionGenerationResult(BaseModel):
    """Resultado de la Justificación del Estudio Previo elaborada por el agente."""
    justificacion_estudio_previo: str = Field(..., description="Texto completo de la justificación técnica, económica y legal")
    documento_soporte_usado: str = Field(..., description="Nombre del archivo de Estudio de Mercado o Propuesta analizado")
    tipo_documento_detectado: str = Field(..., description="ESTUDIO_MERCADO o PROPUESTA")
    analisis_conveniencia_economica: str = Field(..., description="Sustento de razonabilidad de precios y valor de mercado")
    fundamento_juridico_ley_142: str = Field(..., description="Fundamentación jurídica aplicable a ESP")
    marco_juridico_tipologia: Optional[str] = Field(None, description="Marco normativo detallado correspondiente a la tipología contractual")

class NecesidadElaborationInput(BaseModel):
    """Solicitud para estructurar la Descripción de la Necesidad basada en el Objeto y Tipo de Contrato."""
    objeto: str = Field(..., description="Objeto del contrato (determina el análisis técnico y palabras clave)")
    tipologia: str = Field(default="PRESTACION_SERVICIOS", description="PRESTACION_SERVICIOS, SUMINISTRO, OBRA")
    contexto_adicional: Optional[str] = Field(None, description="Contexto adicional o alcance específico")
    items_o_actividades: Optional[List[str]] = Field(default=None, description="Lista exhaustiva del 100% de actividades o bienes (Regla de Inclusión Total)")
    nivel_extension: Optional[str] = Field(default="MEDIA", description="Nivel de extensión: CORTA, MEDIA, COMPLETA")
    instrucciones_adicionales: Optional[str] = Field(None, description="Instrucciones específicas del usuario")
    propuesta_items: Optional[List[Any]] = Field(None, description="Ítems de la propuesta")
    propuesta_texto: Optional[str] = Field(None, description="Texto de la propuesta")

class NecesidadBuildInput(NecesidadElaborationInput):
    """Alias compatible para NecesidadElaborationInput."""
    pass

class ObjetivosGenerationInput(BaseModel):
    """Solicitud para la formulación técnica de Objetivos (General y Específicos)."""
    objeto: str = Field(..., description="Objeto del contrato")
    tipologia: str = Field(default="PRESTACION_SERVICIOS", description="PRESTACION_SERVICIOS, SUMINISTRO, OBRA")
    contexto: Optional[str] = Field(None, description="Contexto adicional o alcance")
    propuesta_items: Optional[List[Any]] = Field(None, description="Lista de ítems o actividades de la propuesta")
    propuesta_texto: Optional[str] = Field(None, description="Texto de la propuesta")
    nivel_extension: Optional[str] = Field(default="MEDIA", description="CORTA, MEDIA, COMPLETA")
    instrucciones_adicionales: Optional[str] = Field(None, description="Instrucciones específicas del usuario")

class ObjetivosGenerationResult(BaseModel):
    """Resultado de Objetivos formulados."""
    objetivo_general: str = Field(..., description="Objetivo general con verbo en infinitivo")
    objetivos_especificos: List[str] = Field(default_factory=list, description="Lista de objetivos específicos técnicos")
    total_especificos: int = 0

class ObligacionesGenerationInput(BaseModel):
    """Solicitud para la estructuración de Obligaciones (Contratista y ESPY)."""
    objeto: str = Field(..., description="Objeto del contrato")
    tipologia: str = Field(default="PRESTACION_SERVICIOS", description="PRESTACION_SERVICIOS, SUMINISTRO, OBRA")
    plazo_ejecucion: Optional[Any] = Field(1, description="Plazo de ejecución numérico o en texto")
    unidad_plazo: Optional[str] = Field("MESES", description="MESES o DIAS")
    plazo_texto: Optional[str] = Field(None, description="Texto completo del plazo")
    tipo_persona: Optional[str] = Field("NATURAL", description="NATURAL o JURIDICA")
    propuesta_items: Optional[List[Any]] = Field(None, description="Ítems o actividades de la propuesta")
    propuesta_texto: Optional[str] = Field(None, description="Texto de la propuesta")
    nivel_extension: Optional[str] = Field(default="MEDIA", description="CORTA, MEDIA, COMPLETA")
    instrucciones_adicionales: Optional[str] = Field(None, description="Instrucciones específicas del usuario")
    valor_total: Optional[float] = Field(None, description="Valor del contrato")

class ObligacionesGenerationResult(BaseModel):
    """Resultado de Obligaciones generadas."""
    obligaciones_especificas: List[str] = Field(default_factory=list)
    obligaciones_generales: List[str] = Field(default_factory=list)
    obligaciones_estudio_previo: List[str] = Field(default_factory=list)
    obligaciones_minuta: List[str] = Field(default_factory=list)
    obligaciones_empresa: List[str] = Field(default_factory=list)

class NecesidadElaborationResult(BaseModel):
    """Estructura de la Necesidad elaborada con base en El Método del Embudo (3 niveles) y la Regla de Inclusión Total."""
    titulo: str = Field(..., description="DESCRIPCIÓN DE LA NECESIDAD A SATISFACER")
    nivel_1: Optional[str] = Field(None, description="Nivel 1: Marco Institucional y misional de la ESPY")
    nivel_2: Optional[str] = Field(None, description="Nivel 2: Brecha Operativa o de Inventario")
    nivel_3: Optional[str] = Field(None, description="Nivel 3: Requerimiento Exacto detallado con fórmula y lista de viñetas (100% de ítems)")
    parrafo_1: Optional[str] = Field(None, description="Compatibilidad: Marco Institucional estándar Ley 142 de 1994")
    parrafo_2: Optional[str] = Field(None, description="Compatibilidad: Brecha operativa o técnica")
    parrafo_3: Optional[str] = Field(None, description="Compatibilidad: Requerimiento detallado con fórmula y viñetas")
    parrafo_4: Optional[str] = Field(default="", description="Compatibilidad: Conclusión de impacto")
    texto_completo: str = Field(..., description="Texto unificado de los 3 niveles con título")


class ObjetoGenerationInput(BaseModel):
    """Solicitud para la formulación automática del Objeto Contractual con posibilidad de edición."""
    document_ids: Optional[List[int]] = Field(default_factory=list, description="Documentos soporte analizados")
    texto_propuesta_o_estudio: Optional[str] = Field(None, description="Texto extraído de la propuesta o estudio")
    tipologia: str = Field(default="PRESTACION_SERVICIOS", description="Tipología contractual de la ESP")
    necesidad_descripcion: Optional[str] = Field(None, description="Descripción inicial del requerimiento")
    contratista_nombre: Optional[str] = Field(None, description="Nombre del contratista")
    lugar_ejecucion: Optional[str] = Field(default="instalaciones y redes de la ESP", description="Delimitación territorial o técnica")

class ObjetoGenerationResult(BaseModel):
    """Objeto contractual sugerido por el agente para revisión y edición libre del usuario."""
    objeto_sugerido: str = Field(..., description="Objeto contractual técnico en infinitivo")
    verbo_rector: str = Field(..., description="Verbo de inicio (Prestar, Construir, Suministrar, etc.)")
    alcance_sintetizado: str = Field(..., description="Síntesis de las actividades principales")
    justificacion_tecnica_objeto: Optional[str] = Field(None, description="Breve explicación de la estructuración del objeto")

class RiskItemSchema(BaseModel):
    """Estructura de cada riesgo contractual conforme a la metodología de Colombia Compra Eficiente (CCE)."""
    numero: int = Field(..., description="Consecutivo numérico sin saltos (1, 2, 3...)")
    clase: str = Field("Específico", description="General o Específico")
    fuente: str = Field("Interno", description="Interno, Externo o Mixto")
    etapa: str = Field("Ejecución", description="Planeación, Precontractual, Ejecución o Liquidación")
    tipo: str = Field(..., description="Operacional, Técnico, Regulatorio, Económico, De la naturaleza, Social o Político, Financiero, Operacional / SST")
    descripcion: str = Field(..., description="Descripción detallada del riesgo previsible")
    consecuencia: str = Field(..., description="Consecuencia de la ocurrencia del riesgo")
    probabilidad_inicial: int = Field(..., description="1 (Raro) a 5 (Casi cierto)")
    impacto_inicial: int = Field(..., description="1 (Insignificante) a 5 (Catastrófico)")
    valoracion_inicial: int = Field(..., description="Valoración = Probabilidad + Impacto inicial")
    categoria_inicial: str = Field(..., description="Bajo (2-4), Medio (5), Alto (6-7), Extremo (8-10)")
    asignacion: str = Field(..., description="A quién se le asigna: Entidad (100% ESPY), Contratista (100%) o Compartido (% / %)")
    tratamiento: str = Field(..., description="Tratamiento, control o medida de mitigación a implementar")
    probabilidad_residual: int = Field(..., description="1 a 5 post-tratamiento")
    impacto_residual: int = Field(..., description="1 a 5 post-tratamiento")
    valoracion_residual: int = Field(..., description="Valoración = Probabilidad + Impacto residual")
    categoria_residual: str = Field(..., description="Bajo (2-4), Medio (5), Alto (6-7), Extremo (8-10)")
    afecta_ejecucion: str = Field("Sí", description="¿Afecta la ejecución del contrato? (Sí/No)")
    responsable: str = Field(..., description="Responsable por implementar el tratamiento")
    monitoreo_mecanismo: str = Field(..., description="¿Cómo se realiza el monitoreo y seguimiento?")
    monitoreo_periodicidad: str = Field(..., description="Periodicidad: En etapa precontractual, Quincenal, Mensual (con informe y cuenta), Al presentarse el evento")

class RiskMatrixInput(BaseModel):
    """Parámetros de entrada para el Agente Especialista en Matrices de Riesgos."""
    contrato_id: Optional[int] = Field(None, description="ID del contrato existente en base de datos si aplica")
    document_ids: Optional[List[int]] = Field(default_factory=list, description="IDs de documentos (Estudio Previo, propuesta, etc.)")
    estudio_previo_texto: Optional[str] = Field(None, description="Texto transcrito o extraído del estudio previo")
    objeto: Optional[str] = Field(None, description="Objeto contractual")
    tipologia: Optional[str] = Field(default="PRESTACION_SERVICIOS", description="PRESTACION_SERVICIOS, SUMINISTRO, OBRA, etc.")
    contratista_nombre: Optional[str] = Field(None, description="Nombre o razón social del contratista")
    valor_estimado: Optional[float] = Field(None, description="Valor del contrato en COP")
    plazo_texto: Optional[str] = Field(None, description="Plazo de ejecución contractual")
    lugar_ejecucion: Optional[str] = Field(None, description="Lugar o condiciones de ejecución territorial en Yolombó")
    exige_polizas: Optional[bool] = Field(None, description="Indica si se exigen pólizas contractuales")
    necesidad_contexto: Optional[str] = Field(None, description="Detalles adicionales del proceso")
    custom_logo_path: Optional[str] = Field(None, description="Ruta o identificador del logo o membrete personalizado si aplica")

class RiskMatrixResult(BaseModel):
    """Matriz de Riesgos integral estructurada y evaluada por el agente especialista."""
    agente_nombre: str = Field(default="Especialista en Gestión y Asignación de Riesgos Previsibles - ESPY S.A. E.S.P.")
    objeto: str = Field(..., description="Objeto contractual técnico corregido e institucional")
    tipologia: str = Field(..., description="PRESTACION_SERVICIOS, SUMINISTRO, OBRA, etc.")
    contratista_nombre: Optional[str] = Field(None, description="Nombre del contratista")
    valor_estimado: Optional[float] = Field(None, description="Valor presupuestal")
    plazo_texto: Optional[str] = Field(None, description="Plazo de ejecución")
    lugar_ejecucion: Optional[str] = Field(None, description="Lugar de ejecución")
    exige_polizas: Optional[bool] = Field(False, description="Exigencia de garantías contractuales")
    insumos_faltantes_advertencias: List[str] = Field(default_factory=list, description="Advertencias sobre insumos indispensables del estudio previo (Paso 1)")
    observaciones_estudio_previo: List[str] = Field(default_factory=list, description="Observaciones y control preventivo sobre el estudio previo")
    riesgos: List[RiskItemSchema] = Field(default_factory=list, description="Lista de riesgos tipificados (14 columnas CCE)")
    total_riesgos: int = Field(0, description="Total de riesgos generados")
    resumen_categorias_inicial: Dict[str, int] = Field(default_factory=dict, description="Conteo de riesgos iniciales por categoría")
    resumen_categorias_residual: Dict[str, int] = Field(default_factory=dict, description="Conteo de riesgos residuales por categoría")
    custom_logo_path: Optional[str] = Field(None, description="Ruta o identificador del logo o membrete personalizado si aplica")


