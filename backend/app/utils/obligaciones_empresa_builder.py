"""Módulo de estructuración y redacción técnica de las 'OBLIGACIONES DE LA EMPRESA (ESPY)'
para Estudios Previos y Minutas Contractuales de la EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ (ESPY).

Reglas de Generación Dinámica:
1. Generar de 2 a 3 Obligaciones Técnicas Específicas de la ESPY (basadas en el Objeto, la Tipología y actividades):
   - Mantenimiento de equipos/herramientas/vehículos:
     Entrega física de los equipos/herramientas a intervenir mediante inventario o relación técnica,
     informar fallas reportadas por el área operativa y verificar pruebas técnicas y repuestos al momento del recibo.
     (PROHIBIDO hablar de 'acceso a plataformas o sistemas').
   - Trabajo de campo / Sensibilización / PGIRS / Socialización:
     Suministrar la programación oficial de rutas, horarios, sectores críticos y lineamientos técnicos ambientales de la ESPY.
   - Suministro / Compraventa de bienes e insumos:
     Efectuar los requerimientos de entrega, disponer del espacio en almacén o planta para la recepción,
     verificar cumplimiento de fichas técnicas/calidad y expedir el ingreso a almacén.
   - Obra / Intervención en redes de acueducto y alcantarillado:
     Entregar el sitio o frente de intervención, suministrar información técnica de las redes existentes
     y verificar las cantidades de obra ejecutadas.
   - Otras tipologías / asesorías técnicas o administrativas:
     Facilitar insumos y antecedentes técnicos requeridos directamente para la labor.

2. Ajustar dinámicamente las Obligaciones Administrativas y de Pago de la ESPY:
   - Terminología del Pago:
     * Si es mantenimiento a todo costo, servicios técnicos operativos, suministro u obra:
       PROHIBIDO usar la palabra 'honorarios'. Usar 'el valor del contrato' o 'el valor de los servicios/bienes ejecutados'.
     * Indicar siempre: 'previa radicación de la factura electrónica o cuenta de cobro (según corresponda al régimen tributario del contratista)'.
   - Coherencia con el Plazo (Regla de Periodicidad):
     * Si el plazo es <= 30 días:
       PROHIBIDO usar 'informes mensuales' o 'pagos mensuales vencidos'.
       Redactar: 'contra entrega y aprobación del informe final de ejecución' y 'revisará el informe de ejecución'.
     * Si el plazo es > 30 días:
       Redactar en términos de informes periódicos o mensuales según el plan de trabajo.
   - Seguridad Social según Tipo de Persona:
     * Si es Persona Jurídica:
       Incluir la verificación de aportes al Sistema de Seguridad Social Integral y Parafiscales (Art. 50 Ley 789 de 2002).
     * Si es Persona Natural:
       Verificación de aportes a Salud, Pensión y ARL (Ley 100 de 1993, Decreto 1273 de 2018).
"""
import re
from typing import List, Optional, Dict, Any


def is_short_term_period(
    plazo_str: Optional[str] = None, 
    plazo_val: Optional[Any] = None, 
    unidad: Optional[str] = None,
    plazo_dias: Optional[Any] = None
) -> bool:
    """
    Determina si el plazo contractual es igual o inferior a 30 días (1 mes o menos).
    """
    if plazo_dias is not None:
        try:
            return float(plazo_dias) <= 30
        except Exception:
            pass

    # 1. Si viene plazo_val y unidad
    if plazo_val is not None:
        try:
            val_num = float(plazo_val)
            u_str = str(unidad or "").strip().lower()
            if "día" in u_str or "dia" in u_str:
                return val_num <= 30
            elif "mes" in u_str:
                return val_num <= 1
        except Exception:
            pass

    # 2. Análisis por expresión de texto
    p_text = str(plazo_str or "").strip().lower()
    if not p_text:
        return False

    # Buscar patrones de días: "15 días", "20 dias", "30 días"
    m_dias = re.search(r"(\d+)\s*d[ií]as?", p_text)
    if m_dias:
        dias = int(m_dias.group(1))
        return dias <= 30

    # Buscar patrones de meses: "1 mes", "un (1) mes"
    m_mes = re.search(r"(\d+)\s*mes(?:es)?", p_text)
    if m_mes:
        meses = int(m_mes.group(1))
        return meses <= 1

    if any(k in p_text for k in ["un (1) mes", "1 mes", "quince (15) días", "veinte (20) días", "treinta (30) días"]):
        return True

    return False


def build_obligaciones_empresa(
    objeto: str,
    tipologia: str = "PRESTACION_SERVICIOS",
    plazo_str: Optional[str] = None,
    plazo_val: Optional[Any] = None,
    unidad_plazo: Optional[str] = None,
    tipo_persona: str = "NATURAL",
    obligaciones_contratista: Optional[List[str]] = None,
    contexto_adicional: Optional[str] = None,
    valor_total: Optional[Any] = None,
    nivel_extension: str = "MEDIA",
    instrucciones_adicionales: Optional[str] = None,
    plazo_dias: Optional[Any] = None,
    **kwargs
) -> List[str]:
    """
    Genera de forma dinámica, técnica y blindada las OBLIGACIONES DE LA EMPRESA (ESPY S.A. E.S.P.)
    para la Minuta Contractual y los Estudios Previos.
    Adapta la profundidad de las obligaciones técnicas según CORTA (2 técnicas), MEDIA (3 técnicas)
    o COMPLETA (4 técnicas detalladas de entrega de insumos/terreno/rutas y verificación conjunta).
    """
    nivel = (nivel_extension or "MEDIA").upper().strip()
    tipo = (tipologia or "PRESTACION_SERVICIOS").upper()
    is_obra = "OBRA" in tipo
    is_suministro = any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"])
    is_arriendo = "ARRENDAMIENTO" in tipo

    obj_text = (objeto or "").lower()
    ctx_text = (contexto_adicional or "").lower()
    full_context = f"{obj_text} {ctx_text}"
    if instrucciones_adicionales:
        full_context += f" {instrucciones_adicionales.lower()}"
    if obligaciones_contratista:
        full_context += " " + " ".join([str(o).lower() for o in obligaciones_contratista])

    # 1. Determinar categoría técnica
    is_gps = any(k in full_context for k in [
        "gps", "telemetr", "adas", "dms", "jc371", "ci05f", "videovigilancia vehicular",
        "cámara vehicular", "camara vehicular", "parque automotor"
    ]) and (is_suministro or "suministro" in full_context or "instalaci" in full_context)

    is_mantenimiento = not is_gps and any(k in full_context for k in [
        "mantenimiento", "herramienta", "eléctric", "electromec", "reparación", "reparacion",
        "taller", "bomba", "motor", "equipo", "maquinaria", "diagnóstico", "diagnostico", "vehículo", "vehiculo"
    ]) and not is_obra

    is_campo_pgirs = any(k in full_context for k in [
        "pgirs", "sensibiliz", "socializ", "puerta a puerta", "ruta selectiva", "residuos",
        "ambiental", "capacitac", "separación en la fuente", "separacion en la fuente", "jornada", "campo"
    ]) and not is_mantenimiento and not is_suministro and not is_obra

    is_redes_obra = is_obra or any(k in full_context for k in [
        "obra civil", "redes", "tubería", "tuberia", "alcantarillado", "acueducto",
        "infraestructura", "pavimento", "concreto", "excavación", "excavacion", "hidráulic", "hidraulic"
    ])

    # 2. Determinar si el plazo es corto (<= 30 días)
    short_term = is_short_term_period(plazo_str=plazo_str, plazo_val=plazo_val, unidad=unidad_plazo, plazo_dias=plazo_dias)

    # 3. Determinar tipo de persona (Jurídica vs Natural)
    is_juridica = str(tipo_persona or "").upper() in ["JURIDICA", "JURÍDICA", "PERSONA_JURIDICA", "NIT"]

    # 4. Determinar si no es honorarios (mantenimiento, servicios técnicos operativos, obra, suministro, trabajo de campo, PGIRS)
    is_non_honorarios = (
        is_mantenimiento or
        is_suministro or
        is_obra or
        is_arriendo or
        is_campo_pgirs or
        any(k in full_context for k in ["operativ", "técnico", "tecnico", "todo costo", "campo", "apoyo a la gestión", "apoyo a la gestion", "pgirs", "sensibiliz", "socializ"])
    )

    # -------------------------------------------------------------------------
    # BLOQUE 1: OBLIGACIONES TÉCNICAS ESPECÍFICAS DE LA ESPY (2 A 4 SEGÚN NIVEL)
    # -------------------------------------------------------------------------
    tecnicas_espy: List[str] = []

    if is_gps:
        tecnicas_espy = [
            "Poner a disposición del contratista, en las fechas y horarios coordinados, los vehículos del parque automotor institucional para realizar la instalación técnica y pruebas de los equipos GPS y cámaras vehiculares.",
            "Verificar en el Almacén General y por conducto del supervisor el estado nuevo, referencias técnicas y correcto funcionamiento de los equipos entregados e instalados, suscribiendo el Acta de Entrada a Almacén y el certificado de recibo a satisfacción.",
            "Designar al personal de la entidad que recibirá la capacitación técnica y las credenciales de administración de la plataforma de monitoreo 24/7.",
            "Designar un supervisor para el control técnico, administrativo y financiero del contrato y efectuar el pago oportuno del valor pactado previa entrega e instalación a satisfacción, radicación de factura electrónica y verificación de seguridad social."
        ]
    elif is_mantenimiento:
        tecnicas_espy = [
            "Hacer entrega física de los equipos, herramientas o bienes a intervenir mediante inventario formal o relación técnica detallada suscrita con el contratista.",
            "Informar oportunamente al contratista las fallas mecánicas, eléctricas o anomalías de operación reportadas por el área operativa de la entidad.",
            "Verificar y presenciar las pruebas técnicas de funcionamiento y certificar la calidad y origen de los repuestos instalados al momento del recibo formal de los equipos.",
            "Facilitar los espacios físicos y condiciones de taller o almacenamiento transitorio en las instalaciones de la ESPY cuando se requiera para diagnósticos conjuntos."
        ]
    elif is_campo_pgirs:
        tecnicas_espy = [
            "Suministrar oportunamente al contratista la programación oficial de rutas, horarios y sectores prioritarios para el desarrollo de las jornadas en campo.",
            "Suministrar la información técnica de los puntos y sectores críticos identificados en la prestación del servicio y los lineamientos técnicos ambientales de la ESPY.",
            "Facilitar los distintivos, formatos institucionales de registro y coordinar el acompañamiento operativo del personal de la entidad en las actividades de socialización.",
            "Coordinar la logística de recolección selectiva y articulación con los recicladores de oficio y vehículos recolectores en el municipio."
        ]
    elif is_suministro:
        tecnicas_espy = [
            "Efectuar oportunamente los requerimientos o solicitudes de entrega de los bienes y materiales conforme a las necesidades operativas de la entidad.",
            "Disponer oportunamente del espacio físico en el Almacén General o plantas de LA EMPRESA para la recepción, descargue e inspección técnica de los bienes suministrados.",
            "Verificar conjuntamente con el supervisor y el responsable de almacén el estricto cumplimiento de las fichas técnicas y estándares de calidad, y expedir la correspondiente Acta de Entrada al Almacén.",
            "Suministrar las especificaciones y lineamientos de rotulado y empaque institucional requeridos para el control de inventarios."
        ]
    elif is_redes_obra:
        tecnicas_espy = [
            "Hacer entrega formal y material al contratista del sitio, frentes de intervención y terrenos requeridos para la ejecución de los trabajos mediante Acta de Entrega de Terreno.",
            "Suministrar la información técnica disponible sobre el trazado de las redes existentes de servicios públicos, planos y especificaciones constructivas de la ESPY.",
            "Efectuar la medición, verificación técnica conjunta y aprobación de las cantidades de obra efectivamente ejecutadas de acuerdo con los ítems contratados.",
            "Gestionar oportunamente los permisos de intervención en vía y autorizaciones técnicas requeridas para el normal avance de los trabajos."
        ]
    elif is_arriendo:
        tecnicas_espy = [
            "Hacer entrega material del bien objeto de arrendamiento mediante inventario formal y suscripción del acta correspondiente.",
            "Garantizar el uso y goce pacífico del bien durante toda la vigencia del contrato, amparando frente a perturbaciones de terceros.",
            "Verificar periódicamente a través de la supervisión el estado de conservación física y destinación autorizada del bien arrendado.",
            "Atender oportunamente las reparaciones locativas o estructurales que legalmente le correspondan conforme al régimen civil."
        ]
    else:
        # Servicios profesionales / administrativos de oficina
        tecnicas_espy = [
            "Suministrar al contratista la información, antecedentes técnicos y documentación institucional estrictamente indispensables para la ejecución autónoma de las labores contratadas.",
            "Coordinar con las diferentes áreas de la entidad la articulación necesaria para el suministro de insumos técnicos que requiera el objeto contractual.",
            "Facilitar el acceso a la información corporativa y antecedentes normativos requeridos para el cumplimiento cabal del servicio."
        ]

    # Filtrar según nivel de extensión
    if nivel == "CORTA":
        tecnicas_espy = tecnicas_espy[:2]
    elif nivel == "COMPLETA":
        tecnicas_espy = tecnicas_espy[:4]
    else:
        # MEDIA: 3 técnicas
        tecnicas_espy = tecnicas_espy[:3]

    # -------------------------------------------------------------------------
    # BLOQUE 2: OBLIGACIONES ADMINISTRATIVAS Y DE PAGO ADAPTADAS
    # -------------------------------------------------------------------------
    admin_espy: List[str] = []

    # 1. Supervisión y revisión de informes
    if short_term:
        ob_sup = (
            "Designar oportunamente un supervisor para realizar el seguimiento, control y verificación técnica "
            "del cumplimiento del objeto contratado, quien revisará el informe final de ejecución y expedirá "
            "la certificación de cumplimiento a satisfacción."
        )
    else:
        ob_sup = (
            "Designar oportunamente un supervisor para ejercer el control, seguimiento técnico y administrativo "
            "de las actividades contratadas, quien revisará periódicamente los informes de ejecución y expedirá "
            "las certificaciones de cumplimiento a satisfacción dentro de los términos establecidos."
        )
    admin_espy.append(ob_sup)

    # 2. Pago y terminología de contraprestación
    # Terminología del pago: "el valor de los honorarios" vs "el valor del contrato / bienes / servicios ejecutados"
    if is_suministro:
        termino_valor = "el valor de los bienes suministrados y recibidos a satisfacción"
    elif is_obra:
        termino_valor = "el valor de las actas de obra ejecutadas y aprobadas"
    elif is_mantenimiento:
        termino_valor = "el valor de los servicios y reparaciones técnicas ejecutadas a todo costo"
    elif is_non_honorarios:
        termino_valor = "el valor de los servicios ejecutados a satisfacción"
    else:
        termino_valor = "el valor de los honorarios profesionales pactados"

    # Radicación de factura o cuenta de cobro según régimen
    radicacion_str = "previa radicación de la factura electrónica o cuenta de cobro (según corresponda al régimen tributario del contratista)"

    # Condición de informes según plazo
    if short_term:
        condicion_informe = "contra entrega y aprobación del informe final de ejecución"
    else:
        condicion_informe = "previa aprobación del correspondiente informe periódico de actividades o ejecución"

    # Verificación de Seguridad Social según persona jurídica vs natural
    if is_juridica:
        ss_str = "verificación de la certificación de aportes al Sistema de Seguridad Social Integral y Parafiscales de conformidad con el artículo 50 de la Ley 789 de 2002 y la Ley 1150 de 2007"
    else:
        ss_str = "verificación de la planilla de pago de aportes al Sistema de Seguridad Social Integral (Salud, Pensión y ARL) de conformidad con la Ley 100 de 1993 y el Decreto 1273 de 2018"

    ob_pago = (
        f"Pagar oportunamente {termino_valor} en las condiciones y plazos acordados, "
        f"{condicion_informe}, {radicacion_str} y {ss_str}."
    )
    admin_espy.append(ob_pago)

    # 3. Autonomía técnica (para servicios / mantenimiento) o facilidades logísticas
    if is_suministro:
        admin_espy.append(
            "Brindar las facilidades de acceso logístico al Almacén General y bodegas de LA EMPRESA para el descargue seguro y custodia de los elementos suministrados."
        )
    elif not is_obra and not is_arriendo:
        admin_espy.append(
            "Respetar la autonomía técnica, administrativa y directiva del contratista en la ejecución del objeto pactado, absteniéndose de impartir órdenes que impliquen subordinación laboral."
        )

    # 4. Trámite de actas
    admin_espy.append(
        "Suscribir oportunamente en debida forma el Acta de Inicio (cuando aplique) y el Acta de Liquidación Final del contrato una vez culminadas las obligaciones contractuales y verificado el paz y salvo integral."
    )

    # Consolidar admin_espy según nivel de extensión
    if nivel == "CORTA":
        # CORTA: 2 técnicas + 2 esenciales de supervisión y pago = 4 en total
        admin_final = [ob_sup, ob_pago]
    elif nivel == "COMPLETA":
        # COMPLETA: 4 técnicas + 4 administrativas y de control = hasta 7-8 en total
        admin_final = list(admin_espy)
    else:
        # MEDIA: 3 técnicas + administrativas estándar
        admin_final = list(admin_espy)

    # Consolidar lista completa
    resultado_final = list(tecnicas_espy) + list(admin_final)

    # Limpiar posibles duplicados preservando orden
    seen = set()
    dedup: List[str] = []
    for item in resultado_final:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            dedup.append(cleaned)

    return dedup


def build_forma_pago_clausula(
    tipologia: str = "PRESTACION_SERVICIOS",
    objeto: str = "",
    plazo_str: Optional[str] = None,
    plazo_val: Optional[Any] = None,
    unidad_plazo: Optional[str] = None,
    tipo_persona: str = "NATURAL",
    forma_pago_custom: Optional[str] = None,
    valor_total: Optional[Any] = None,
    **kwargs
) -> str:
    """
    Construye la redacción armonizada de la FORMA DE PAGO para la Cláusula Segunda de la Minuta
    y la sección correspondiente en Estudios Previos.
    Aplica la Regla de Periodicidad: si el plazo es <= 30 días, PROHIBIDO hablar de 'mensuales'.
    Aplica la Regla de Terminología: NO usar 'honorarios' en mantenimiento/técnico/suministro/obra.
    """
    if forma_pago_custom and str(forma_pago_custom).strip():
        # Si el usuario o la propuesta suministró una forma de pago explícita
        fp = str(forma_pago_custom).strip()
        # Si el plazo es corto y trae "mensual", sanearlo
        if is_short_term_period(plazo_str, plazo_val, unidad_plazo):
            fp = re.sub(r"\bpagos?\s+mensuales?\s+(?:vencidos?)?\b", "Pago único", fp, flags=re.IGNORECASE)
            fp = re.sub(r"\binformes?\s+mensuales?\b", "informe final de ejecución", fp, flags=re.IGNORECASE)
            fp = re.sub(r"\bmensualmente\b", "contra entrega", fp, flags=re.IGNORECASE)
        return fp

    short_term = is_short_term_period(plazo_str, plazo_val, unidad_plazo)
    tipo = (tipologia or "PRESTACION_SERVICIOS").upper()
    is_suministro = any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"])
    is_obra = "OBRA" in tipo
    is_juridica = str(tipo_persona or "").upper() in ["JURIDICA", "JURÍDICA", "PERSONA_JURIDICA", "NIT"]

    ss_clause = "certificación de aportes a Seguridad Social Integral y Parafiscales (Art. 50 Ley 789 de 2002)" if is_juridica else "planillas de pago de aportes a Seguridad Social Integral (Salud, Pensión y ARL)"

    if is_suministro:
        if short_term:
            return f"Pago único contra entrega material a satisfacción del 100% de los bienes en el Almacén General de LA EMPRESA, previa suscripción del Acta de Entrada al Almacén, radicación de la factura electrónica validada por la DIAN (o cuenta de cobro) y verificación de {ss_clause}."
        else:
            return f"Pagos parciales contra entregas periódicas de bienes en el Almacén General de LA EMPRESA, previa suscripción de las Actas de Entrada al Almacén, radicación de la factura electrónica validada por la DIAN y verificación de {ss_clause}."

    if is_obra:
        return f"Mediante actas parciales de obra mensualizadas según avance físico y cuadro de cantidades ejecutadas debidamente aprobadas por la interventoría/supervisión técnica, amortización de anticipo (si aplica), radicación de factura electrónica y verificación de {ss_clause}; y un acta de liquidación y recibo final."

    # Servicios / Mantenimiento
    if short_term:
        return f"Pago único contra entrega y aprobación del informe final de ejecución técnica por parte del supervisor designado por LA EMPRESA, previa radicación de la factura electrónica o cuenta de cobro (según el régimen tributario del contratista) y verificación de {ss_clause}."
    else:
        return f"Pagos mensuales vencidos previa presentación y aprobación del informe de actividades por parte de la supervisión, radicación de la factura electrónica o cuenta de cobro (según el régimen tributario del contratista) y verificación de {ss_clause}."
