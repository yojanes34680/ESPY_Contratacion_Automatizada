"""Módulo de estructuración y redacción técnica de las 'OBLIGACIONES DEL CONTRATISTA'
(Obligaciones Específicas y Obligaciones Generales/Administrativas) para
Estudios Previos y Minutas Contractuales de la EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ (ESPY).

Regla de Simetría y Verbos Rectores:
Toda actividad identificada en la Descripción de la Necesidad debe convertirse en una obligación
contractual exigible. Cada obligación debe iniciar con un verbo en infinitivo (Ejecutar, Suministrar,
Realizar, Garantizar, Entregar, Presentar) y debe redactarse de tal forma que el supervisor del
contrato pueda verificar su cumplimiento mediante un soporte físico o verificable.

Paso 1: Reglas de Transformación para las OBLIGACIONES ESPECÍFICAS (Según el tipo de insumo)
- ESCENARIO A (Propuesta Detallada con múltiples ítems >= 3):
  Regla de Inclusión Total: Convierte el 100% de las actividades o bienes propuestos en obligaciones
  específicas individuales. Está ESTRICTAMENTE PROHIBIDO omitir, agrupar o resumir ítems de la propuesta.

- ESCENARIO B (Cotización Escueta o de Una Sola Línea - Ej: 'Mantenimiento a todo costo', 'Suministro global'):
  ¡PROHIBIDO dejar una sola obligación específica! Debes proteger jurídicamente a la ESPY desglosando
  ese renglón único en mínimo 6 a 8 obligaciones específicas técnicas y de control, asegurando que incluyan:
  1. La obligación principal literal según la cotización.
  2. El diagnóstico o levantamiento previo de información/estado inicial.
  3. La ejecución técnica detallada (preventiva/correctiva o entrega material).
  4. La cláusula de 'Todo Costo' o calidad de insumos (repuestos/materiales nuevos, originales o de primera calidad, asumiendo costos directos e indirectos).
  5. Las pruebas de funcionamiento y entrega a satisfacción al almacén o supervisor.
  6. La exigencia de soportes técnicos detallados (fichas técnicas, registro fotográfico antes/después, relación de repuestos) como requisito indispensable para el pago.
  7. La garantía técnica sobre el trabajo realizado o los bienes suministrados.

Paso 2: Inclusión de OBLIGACIONES GENERALES Y ADMINISTRATIVAS (Blindaje de Supervisión)
Bloque administrativo estándar adaptado a la tipología contractual:
- Suscripción oportuna del Acta de Inicio, Actas Parciales y Acta de Liquidación/Recibo Final.
- Presentación de informes de ejecución detallados con evidencias verificables (planillas, fotos, remisiones).
- Acreditación mensual de aportes al Sistema de Seguridad Social Integral (Salud, Pensión, ARL) y Parafiscales (Art. 50 Ley 789/2002 y Ley 1150/2007).
- Cumplimiento de normas SST y uso de Elementos de Protección Personal (EPP).
- Atención oportuna a requerimientos, observaciones y reuniones del supervisor del contrato.
"""
import re
from typing import List, Optional, Dict, Any
from app.utils.objective_normalizer import clean_technical_text, starts_with_infinitive
from app.utils.necesidad_builder import extract_items_from_text, _is_valid_item, _clean_action_from_objeto


INFINITIVE_VERBS_RE = re.compile(
    r"^(?:ejecutar|suministrar|realizar|garantizar|entregar|presentar|acreditar|disponer|implementar|"
    r"cumplir|acatar|atender|elaborar|suscribir|verificar|instalar|adecuar|reparar|dotar|informar|"
    r"adoptar|asistir|reemplazar|efectuar|prestar|mantener|custodiar|responder|tramitar|proteger|"
    r"transportar|desarrollar|estructurar|certificar|reponer|restituir|diligenciar|constituir|permitir|"
    r"guardar|obrar|ceder|abastecer|organizar|capacitar|destinar)\b",
    re.IGNORECASE
)



def format_obligation_infinitive(text: str, default_verb: str = "Ejecutar") -> str:
    """
    Convierte una actividad o texto en una obligación formal iniciando OBLIGATORIAMENTE
    con un verbo en infinitivo (Ejecutar, Suministrar, Realizar, Garantizar, Entregar, Presentar, etc.)
    y con puntuación final de punto.
    """
    s = clean_technical_text(text)
    if not s:
        return ""

    from app.utils.necesidad_builder import clean_ocr_joined_words, clean_signature_footers
    s = clean_ocr_joined_words(s)
    s = clean_signature_footers(s)

    # Quitar viñetas, números y espacios
    s = re.sub(r"^[\-\•\*\s\d\.\,\)]+", "", s).strip()

    # Si ya inicia con verbo rector en infinitivo
    m_verb = INFINITIVE_VERBS_RE.match(s)
    if m_verb or starts_with_infinitive(s):
        res = s[0].upper() + s[1:]
        return res if res.endswith(".") else f"{res}."

    # Transformaciones idiomáticas de sustantivos a verbos en infinitivo
    patterns = [
        (r"^(?:suministro,?\s*transporte\s*e\s*instalaci[oó]n|suministro\s+e\s+instalaci[oó]n)\s+(?:de\s+)?", "Suministrar e instalar "),
        (r"^(?:suministro,?\s*transporte\s+y\s+entrega|suministro\s+y\s+entrega)\s+(?:de\s+)?", "Suministrar, transportar y entregar "),
        (r"^suministro\s+(?:de\s+)?", "Suministrar "),
        (r"^mantenimiento\s+(?:preventivo\s+y\s+correctivo|a\s+todo\s+costo|preventivo|correctivo)?\s+(?:de|a)\s+", "Realizar el mantenimiento a todo costo de "),
        (r"^mantenimiento\s+(?:de|a)\s+", "Realizar el mantenimiento de "),
        (r"^diagn[oó]stico\s+(?:t[eé]cnico\s+)?(?:de\s+)?", "Realizar el diagnóstico técnico de "),
        (r"^ejecuci[oó]n\s+(?:de\s+)?", "Ejecutar "),
        (r"^elaboraci[oó]n\s+(?:de\s+)?", "Elaborar "),
        (r"^presentaci[oó]n\s+(?:de\s+)?", "Presentar "),
        (r"^entrega\s+(?:de\s+)?", "Entregar "),
        (r"^instalaci[oó]n\s+(?:de\s+)?", "Instalar "),
        (r"^construcci[oó]n\s+(?:de\s+)?", "Construir "),
        (r"^adecuaci[oó]n\s+(?:de\s+)?", "Adecuar "),
        (r"^reparaci[oó]n\s+(?:de\s+)?", "Reparar "),
        (r"^adquisici[oó]n\s+(?:de\s+)?", "Suministrar y entregar "),
        (r"^verificaci[oó]n\s+(?:de\s+)?", "Verificar "),
        (r"^revisi[oó]n\s+(?:de\s+)?", "Revisar "),
        (r"^capacitaci[oó]n\s+(?:de\s+|en\s+)?", "Capacitar en "),
        (r"^asistencia\s+(?:a\s+|en\s+)?", "Asistir a "),
        (r"^apoyo\s+(?:a\s+|en\s+)?", "Brindar apoyo técnico y operativo en "),
        (r"^acreditaci[oó]n\s+(?:de\s+)?", "Acreditar "),
        (r"^implementaci[oó]n\s+(?:de\s+)?", "Implementar "),
        (r"^transporte\s+(?:de\s+)?", "Transportar "),
        (r"^disposici[oó]n\s+final\s+(?:de\s+)?", "Efectuar la disposición final adecuada de "),
    ]

    for pat, repl in patterns:
        if re.search(pat, s, re.IGNORECASE):
            s = re.sub(pat, repl, s, count=1, flags=re.IGNORECASE).strip()
            res = s[0].upper() + s[1:]
            return res if res.endswith(".") else f"{res}."

    # Si no coincidió con ningún patrón, anteponer verbo por defecto
    s_clean = re.sub(r"^(?:el|la|los|las)\s+", "", s, flags=re.IGNORECASE).strip()
    res = f"{default_verb} {s_clean[0].lower() + s_clean[1:]}"
    res = res[0].upper() + res[1:]
    return res if res.endswith(".") else f"{res}."


def get_obligaciones_generales_administrativas(
    tipologia: str = "PRESTACION_SERVICIOS",
    nivel_extension: str = "MEDIA"
) -> List[str]:
    """
    Retorna el bloque de OBLIGACIONES GENERALES Y ADMINISTRATIVAS de blindaje de supervisión
    de la ESPY, adaptadas a la tipología contractual y nivel de extensión:
    - CORTA: 4 esenciales (Actas, Informes/evidencias, Seguridad social, SST).
    - MEDIA: 5 estándar institucional.
    - COMPLETA: Bloque ampliado de 7 obligaciones generales (incluyendo reserva, indemnidad, requerimientos, comités).
    """
    nivel = (nivel_extension or "MEDIA").upper().strip()
    tipo = (tipologia or "PRESTACION_SERVICIOS").upper()
    is_obra = "OBRA" in tipo
    is_suministro = any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"])
    is_arriendo = "ARRENDAMIENTO" in tipo

    obligaciones_generales = [
        "Suscribir oportunamente en debida forma el Acta de Inicio, Actas Parciales de avance o recibo y el Acta de Liquidación Definitiva del contrato en coordinación directa con el supervisor designado por la ESPY.",
        "Presentar informes periódicos y mensuales de ejecución detallados acompañados de evidencias físicas y verificables (planillas de registro, informes de actividades, bitácoras, registros fotográficos y remisiones técnicas) como requisito previo para la expedición de certificaciones de cumplimiento y trámite de pago.",
        "Acreditar oportunamente y de manera mensual el pago de aportes al Sistema de Seguridad Social Integral (Salud, Pensión, ARL en el nivel de riesgo reglamentario) y Parafiscales de todo el personal vinculado a la ejecución contractual, de conformidad con el artículo 50 de la Ley 789 de 2002, la Ley 1150 de 2007 y el Decreto 1273 de 2018.",
        "Cumplir estrictamente con las normas, planes y directrices del Sistema de Gestión de la Seguridad y Salud en el Trabajo (SG-SST) conforme al Decreto 1072 de 2015 y la Resolución 0312 de 2019, garantizando el suministro y uso permanente de los Elementos de Protección Personal (EPP/EPI) reglamentarios para trabajos en campo, planta o taller.",
        "Atender oportuna, eficaz y diligentemente los requerimientos, observaciones técnicas, solicitudes de ajuste y convocatorias a reuniones o comités citados por el supervisor del contrato, garantizando permanente disponibilidad y comunicación técnica."
    ]

    if is_obra:
        obligaciones_generales.extend([
            "Diligenciar diariamente y mantener actualizada la bitácora o libro oficial de obra en conjunto con la interventoría/supervisión técnica, registrando frentes de trabajo, personal, clima e incidencias.",
            "Constituir, prorrogar y mantener vigentes todas las garantías contractuales exigidas (cumplimiento, salarios y prestaciones sociales, estabilidad de obra y responsabilidad civil extracontractual)."
        ])
    elif is_suministro:
        obligaciones_generales.extend([
            "Suscribir formalmente el Acta de Entrada al Almacén y Recibo a Satisfacción conjuntamente con el Jefe de Almacén y el Supervisor del contrato tras la verificación física, conteo y pruebas técnicas de los bienes.",
            "Mantener indemne a la ESPY frente a cualquier reclamación de terceros por infracción de patentes, marcas o defectos atribuibles a los bienes suministrados."
        ])
    elif is_arriendo:
        obligaciones_generales.extend([
            "Permitir la inspección periódica del inmueble por parte del supervisor designado por la ESPY para verificar su estado de conservación y destinación.",
            "Restituir formalmente el inmueble a la ESPY al vencimiento del plazo contractual mediante acta de entrega y recibo final a satisfacción."
        ])
    else:
        obligaciones_generales.extend([
            "Ejecutar las actividades con plena autonomía técnica, administrativa y directiva, sin subordinación jurídica ni laboral con la ESPY, en los términos del régimen de derecho privado de la Ley 142 de 1994 y el Artículo 23 del Código Sustantivo del Trabajo.",
            "Guardar estricta reserva y confidencialidad sobre la información técnica, administrativa y bases de datos a las que tenga acceso, en cumplimiento de la Ley 1581 de 2012 de Protección de Datos Personales."
        ])

    if nivel == "CORTA":
        return obligaciones_generales[:4]
    elif nivel == "COMPLETA":
        return obligaciones_generales[:7]
    else:
        return obligaciones_generales[:5]


def generate_escenario_b_obligaciones_especificas(
    item_principal: str,
    objeto: str,
    tipologia: str = "PRESTACION_SERVICIOS",
    nivel_extension: str = "MEDIA",
    instrucciones_adicionales: Optional[str] = None
) -> List[str]:
    """
    ESCENARIO B: Cotización Escueta o de Una Sola Línea.
    Desglosa el ítem único en un bloque técnico de mínimo 6 a 8 obligaciones específicas
    técnicas y de control para proteger jurídicamente a la ESPY:
    1. Obligación principal literal según la cotización (con verbo en infinitivo).
    2. Diagnóstico o levantamiento previo de información/estado inicial.
    3. Ejecución técnica detallada (preventiva/correctiva o entrega material).
    4. Cláusula de 'Todo Costo' o calidad de insumos (repuestos/materiales nuevos, originales, asumiendo costos directos e indirectos).
    5. Pruebas de funcionamiento y entrega a satisfacción al almacén o supervisor.
    6. Exigencia de soportes técnicos detallados (fichas por equipo, registro fotográfico antes y después, relación de repuestos) como requisito indispensable para el pago.
    7. Garantía técnica sobre el trabajo realizado o bienes suministrados.
    """
    tipo = (tipologia or "PRESTACION_SERVICIOS").upper()
    is_suministro = any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"])
    item_full = f"{item_principal} {objeto}".lower()

    # Formatear la obligación principal literal
    main_ob = format_obligation_infinitive(item_principal, default_verb="Suministrar" if is_suministro else "Ejecutar")

    # Rama prioritaria para GPS / Videovigilancia Vehicular / Telemetría (antes que herramientas/equipos)
    if any(k in item_full for k in ["gps", "telemetr", "adas", "dms", "jc371", "ci05f", "videovigilancia vehicular", "cámara vehicular", "camara vehicular"]):
        especificas = [
            "Suministrar y entregar en el Almacén General de la ESPY dos (2) unidades de rastreo satelital GPS LC, dos (2) unidades de video vehicular Ref. JC371 con cámara frontal ADAS, dos (2) cámaras internas de cabina CI05F Cabin-View Full AHD DMS, dos (2) tarjetas MicroSD de 128 GB y sus accesorios de control y seguridad en cabina (bloqueo remoto de motor, botón de pánico, sirena de velocidad, parlante y solicitud de llamada), completamente nuevos y originales de fábrica.",
            "Ejecutar en sitio la instalación técnica especializada, cableado estructurado automotriz y configuración de las unidades GPS, cámaras ADAS/DMS y periféricos en los vehículos del parque automotor de la ESPY, asumiendo todos los costos de desplazamiento y viáticos.",
            "Habilitar, integrar y garantizar la operatividad continua durante el período pactado del servicio conexo de monitoreo en plataforma web y aplicación móvil 24/7, configurando perfiles de usuario, geocercas, control de rutas e itinerarios, alertas de velocidad, identificación electrónica de conductores, test preoperacional e indicadores de gestión del PESV.",
            "Brindar capacitación técnica y apoyo logístico al personal designado por la ESPY en el manejo de la plataforma web/móvil y analítica de informes, así como otorgar y responder por las garantías técnicas de fábrica de los equipos y accesorios suministrados.",
            "Suscribir oportunamente el Acta de Inicio, Acta de Entrada a Almacén, Acta de Recibo a Satisfacción y Acta de Liquidación Final, presentar factura electrónica validada por la DIAN y acreditar el pago de aportes al Sistema de Seguridad Social Integral y Parafiscales (Art. 50 Ley 789 de 2002)."
        ]
    elif any(k in item_full for k in ["herramienta", "eléctric", "electromec", "equipo", "maquinaria", "motor", "bomba", "planta", "taller"]):
        especificas = [
            main_ob,
            "Realizar el diagnóstico técnico previo y levantamiento del estado inicial de operatividad, desgaste mecánico, aislamiento eléctrico y fallas de cada una de las herramientas y equipos entregados para intervención.",
            "Ejecutar el mantenimiento preventivo y correctivo especializado a nivel mecánico y eléctrico, incluyendo labores de desensamble integral, limpieza química de componentes, lubricación de partes motrices y calibración técnica.",
            "Suministrar e instalar a todo costo la totalidad de los repuestos, accesorios, devanados, rodamientos y consumibles necesarios para la reparación, garantizando que sean completamente nuevos, legítimos u originales de fábrica, asumiendo el contratista todos los costos directos e indirectos.",
            "Realizar las pruebas técnicas de funcionamiento, aislamiento dieléctrico, torque y rendimiento bajo carga real de trabajo previas a la entrega, certificando que los equipos operen dentro de los parámetros de diseño del fabricante.",
            "Entregar a entera satisfacción en las instalaciones de la ESPY las herramientas y equipos debidamente embalados, rotulados y en óptimas condiciones de disponibilidad y seguridad operativa.",
            "Presentar a la supervisión, como requisito indispensable y previo para el trámite de pago, los soportes técnicos individuales consistentes en fichas técnicas por equipo intervenido, memoria de diagnóstico, relación de repuestos cambiados y registro fotográfico comparativo del antes y después.",
            "Garantizar técnicamente los trabajos de mantenimiento realizados y los repuestos suministrados por un período mínimo de tres (3) meses, asumiendo sin costo alguno para la ESPY la atención prioritaria de cualquier reincidencia o desperfecto dentro de las veinticuatro (24) horas siguientes al reporte."
        ]
    elif any(k in item_full for k in ["vehículo", "vehiculo", "transporte", "volqueta", "camion", "camión", "arrendamiento"]):
        especificas = [
            main_ob,
            "Realizar la inspección técnica preoperacional y levantamiento del estado físico, mecánico y documental del vehículo previo a la suscripción del acta de entrega e inicio.",
            "Garantizar la disponibilidad operativa continua del vehículo automotor para la movilización de personal operativo, herramientas y materiales requeridos para la atención de contingencias de acueducto, alcantarillado y aseo.",
            "Asumir a todo costo el mantenimiento preventivo y correctivo integral del automotor, incluyendo cambios de aceite, fluidos, llantas, repuestos y servicio técnico mecánico calificado para prevenir parálisis operativas.",
            "Suministrar e incorporar insumos, lubricantes y repuestos de primera calidad y especificaciones recomendadas por el fabricante del automotor, asumiendo el contratista los costos directos e indirectos derivados.",
            "Acreditar y mantener vigentes durante todo el término del contrato el SOAT, la revisión técnico-mecánica y de gases, pólizas de responsabilidad civil contractual y extracontractual y demás permisos legales de circulación.",
            "Efectuar la entrega de bitácoras de recorrido diarias, planillas de control de kilometraje/horas de servicio y reportes técnicos de disponibilidad técnica firmados por los conductores autorizados y el supervisor.",
            "Garantizar la sustitución inmediata del vehículo por otro de similares o superiores características técnicas en un lapso no superior a veinticuatro (24) horas ante eventuales fallas mecánicas, siniestros o mantenimientos mayores.",
            "Presentar mensualmente a la supervisión la relación discriminada de servicios, reportes de disponibilidad técnica y evidencias documentales como requisito indispensable para la liquidación y pago del canon mensual."
        ]
    elif any(k in item_full for k in ["papelería", "papeleria", "aseo", "cafetería", "insumos de oficina", "útiles", "utiles"]):
        especificas = [
            main_ob,
            "Efectuar el levantamiento técnico y verificación inicial del catálogo de insumos y referencias requeridas por las diferentes dependencias de la ESPY.",
            "Suministrar bienes, papelería y útiles de primera calidad, de marcas reconocidas en el mercado y cumpliendo estrictamente con las especificaciones técnicas solicitadas.",
            "Garantizar la condición de entrega a todo costo en el Almacén General de la ESPY, asumiendo fletes, seguros de transporte, empaque, cargue y descargue seguro de los bienes.",
            "Realizar las entregas materiales en los plazos y órdenes de pedido emitidas por la supervisión, en óptimas condiciones de embalaje y rotulado.",
            "Realizar la verificación conjunta con el Almacenista y el supervisor del contrato, confrontando cantidades, marcas y calidades contra remisión y factura.",
            "Presentar las remisiones detalladas debidamente suscritas por el encargado de almacén y las fichas técnicas como requisito indispensable para la radicación de la cuenta de cobro o factura.",
            "Garantizar técnicamente los bienes suministrados, obligándose a reponer en un término máximo de cuarenta y ocho (48) horas cualquier elemento averiado, defectuoso o que no cumpla los estándares exigidos."
        ]
    elif is_suministro:
        especificas = [
            main_ob,
            "Realizar el levantamiento previo de especificaciones técnicas, normas de fabricación y cronograma de despachos coordinado con la supervisión técnica de la ESPY.",
            "Suministrar bienes y materiales totalmente nuevos, de primera calidad, de fabricación reciente y que cumplan rigurosamente las normas técnicas aplicables (NTC, AWWA, ASTM, ISO).",
            "Efectuar el transporte, cargue, flete, seguro y descargue bajo la modalidad DDP (Delivered Duty Paid) en el Almacén General de la ESPY, asumiendo todos los costos directos e indirectos.",
            "Realizar pruebas de verificación técnica, inspección física y cotejo de cantidades y lotes conjuntamente con el funcionario de Almacén y el Supervisor.",
            "Entregar los catálogos oficiales, fichas técnicas, hojas de seguridad (MSDS/SGA cuando aplique) y certificados de control de calidad de fábrica de los lotes suministrados.",
            "Presentar las remisiones de entrega a satisfacción debidamente firmadas por el almacenista y las pólizas de garantía de fábrica como requisito previo e indispensable para el trámite de pago.",
            "Otorgar garantía técnica formal sobre los bienes por un periodo no inferior a doce (12) meses, obligándose a reponer a su costo cualquier elemento con fallas de fabricación en un término no superior a cuarenta y ocho (48) horas."
        ]
    else:
        especificas = [
            main_ob,
            "Realizar el diagnóstico técnico preliminar y levantamiento detallado de la información inicial y requerimientos operativos para la formulación del plan de trabajo.",
            "Ejecutar de forma oportuna y con plena autonomía las actividades técnicas y operativas especializadas conforme a las directrices y cronogramas aprobados por la ESPY.",
            "Suministrar y disponer a todo costo de la totalidad de las herramientas, equipos de diagnóstico, transporte e insumos técnicos necesarios para la ejecución cabal de las labores.",
            "Garantizar la calidad e idoneidad técnica en cada una de las actividades desarrolladas, aplicando las mejores prácticas operativas y normativas técnicas de la ESPY.",
            "Efectuar las verificaciones y pruebas técnicas de funcionamiento y control de calidad requeridas para validar los resultados obtenidos.",
            "Elaborar y presentar a la supervisión del contrato, como requisito obligatorio para el trámite de pago, los informes periódicos con soportes documentales, planillas de campo, memorias técnicas y registro fotográfico detallado.",
            "Garantizar la estabilidad, calidad y soporte técnico sobre los entregables y actividades ejecutadas durante todo el plazo de ejecución del contrato."
        ]

    nivel = (nivel_extension or "MEDIA").upper().strip()
    if instrucciones_adicionales:
        inst_clean = instrucciones_adicionales.strip()
        extra_ob = format_obligation_infinitive(f"Cumplir con la instrucción prioritaria de {inst_clean}", default_verb="Garantizar")
        if extra_ob and extra_ob not in especificas:
            especificas.append(extra_ob)

    if nivel == "CORTA":
        # Mínimo 6 obligaciones específicas directas según AGENTS.md
        return especificas[:6]
    elif nivel == "COMPLETA":
        # Redacción pormenorizada con alto blindaje (8 a 10 obligaciones)
        return especificas
    else:
        # MEDIA: 6 a 8 obligaciones
        return especificas[:8]


def build_obligaciones_contratista(
    objeto: str,
    tipologia: str = "PRESTACION_SERVICIOS",
    items_propuesta: Optional[List[str]] = None,
    contexto_adicional: Optional[str] = None,
    nivel_extension: str = "MEDIA",
    instrucciones_adicionales: Optional[str] = None,
    propuesta_items: Optional[List[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Estructura integralmente las OBLIGACIONES DEL CONTRATISTA para Estudios Previos y Minutas:
    - OBLIGACIONES ESPECÍFICAS (aplicando Escenario A o Escenario B, moduladas por CORTA, MEDIA o COMPLETA).
    - OBLIGACIONES GENERALES Y ADMINISTRATIVAS (blindaje de supervisión adaptado a tipología y nivel).
    - Formateo listo para Estudios Previos y Minuta contractual con 100% de verbos en infinitivo.
    """
    effective_items = propuesta_items if propuesta_items is not None else items_propuesta
    nivel = (nivel_extension or "MEDIA").upper().strip()
    tipo = (tipologia or "PRESTACION_SERVICIOS").upper()
    is_suministro = any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"])

    # 1. Obtener ítems candidatos del insumo
    raw_items = list(effective_items or [])
    if not raw_items and contexto_adicional:
        raw_items = extract_items_from_text(contexto_adicional)

    valid_items = [it for it in raw_items if _is_valid_item(it)]

    # 2. Determinar si es Escenario A o Escenario B
    if len(valid_items) >= 3:
        # ESCENARIO A: Regla de Inclusión Total (100% de ítems convertidos en obligaciones específicas individuales)
        default_verb = "Suministrar" if is_suministro else "Ejecutar"
        obligaciones_especificas = []
        for it in valid_items:
            if nivel == "CORTA":
                ob = format_obligation_infinitive(it, default_verb=default_verb)
            elif nivel == "COMPLETA":
                # Ampliación técnica con estándares de calidad y soporte
                ob_base = format_obligation_infinitive(it, default_verb=default_verb).rstrip(".")
                if is_suministro:
                    ob = f"{ob_base}, asegurando óptima calidad de fábrica, rotulado, empaque y entrega bajo la modalidad DDP en el Almacén General de la ESPY con sus respectivas fichas técnicas."
                else:
                    ob = f"{ob_base}, cumpliendo con las normas técnicas sectoriales aplicables, estándares de calidad y entregando los respectivos reportes técnicos y registro fotográfico a satisfacción de la supervisión."
            else:
                # MEDIA
                ob = format_obligation_infinitive(it, default_verb=default_verb)

            if ob and ob not in obligaciones_especificas:
                obligaciones_especificas.append(ob if ob.endswith(".") else f"{ob}.")

        if instrucciones_adicionales:
            inst_clean = instrucciones_adicionales.strip()
            extra_ob = format_obligation_infinitive(f"Atender prioritariamente la instrucción técnica consistente en {inst_clean}", default_verb="Garantizar")
            if extra_ob and extra_ob not in obligaciones_especificas:
                obligaciones_especificas.append(extra_ob)
    else:
        # ESCENARIO B: Cotización Escueta o de Una Sola Línea
        item_base = valid_items[0] if valid_items else _clean_action_from_objeto(objeto)
        if not item_base:
            item_base = objeto or "la ejecución de las actividades técnicas contratadas"
        obligaciones_especificas = generate_escenario_b_obligaciones_especificas(
            item_principal=item_base,
            objeto=objeto,
            tipologia=tipo,
            nivel_extension=nivel,
            instrucciones_adicionales=instrucciones_adicionales
        )

    # 3. Obtener OBLIGACIONES GENERALES Y ADMINISTRATIVAS
    obligaciones_generales = get_obligaciones_generales_administrativas(tipo, nivel_extension=nivel)

    # 4. Consolidar para Estudio Previo y Minuta
    obligaciones_consolidadas = list(obligaciones_especificas) + list(obligaciones_generales)

    texto_estructurado = (
        "OBLIGACIONES DEL CONTRATISTA\n\n"
        "A. OBLIGACIONES ESPECÍFICAS:\n"
        + "\n".join(f"{idx + 1}. {ob}" for idx, ob in enumerate(obligaciones_especificas))
        + "\n\nB. OBLIGACIONES GENERALES Y ADMINISTRATIVAS:\n"
        + "\n".join(f"{idx + 1}. {ob}" for idx, ob in enumerate(obligaciones_generales))
    )

    return {
        "obligaciones_especificas": obligaciones_especificas,
        "obligaciones_generales": obligaciones_generales,
        "obligaciones_minuta": obligaciones_consolidadas,
        "obligaciones_estudio_previo": obligaciones_consolidadas,
        "texto_estructurado": texto_estructurado,
        "escenario_detectado": "ESCENARIO_A" if len(valid_items) >= 3 else "ESCENARIO_B",
        "total_especificas": len(obligaciones_especificas),
        "total_generales": len(obligaciones_generales),
        "total_obligaciones": len(obligaciones_consolidadas)
    }
