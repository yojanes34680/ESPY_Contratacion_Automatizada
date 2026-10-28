"""Módulo de estructuración y redacción técnica de 'OBJETIVO GENERAL' y 'OBJETIVOS ESPECÍFICOS'
para Estudios Previos y documentos contractuales de la EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ (ESPY).

REGLAS PROHIBITIVAS ESTRICTAS:
1. PROHIBIDO concatenar o incrustar literalmente el objeto del contrato en mayúsculas dentro de frases genéricas
   (NUNCA: 'Asegurar las labores para PRESTACIÓN DE SERVICIOS DE...').
   Se debe integrar el sentido del objeto de forma natural, con redacción fluida y en minúsculas (salvo nombres propios o siglas como ESPY o PGIRS).
2. PROHIBIDO poner trámites administrativos como objetivos específicos:
   NUNCA incluir 'presentar informes mensuales', 'pasar cuentas de cobro', 'asistir a reuniones' o 'pagar seguridad social'.
   Esas son obligaciones administrativas, no objetivos técnicos del proyecto.
3. PROHIBIDO usar frases comodín vacías:
   NUNCA usar viñetas como 'Ejecutar las actividades programadas en los plazos fijados'.
   Cada objetivo específico debe hablar de la materia técnica real del contrato (agua, herramientas, redes, residuos, software, asesoría jurídica, etc.).

ESTRUCTURA DE REDACCIÓN OBLIGATORIA:
1. OBJETIVO GENERAL (El "Qué" + El "Para qué misional"):
   - Un solo párrafo contundente que inicie con un verbo en infinitivo de alto nivel:
     (Garantizar, Fortalecer, Optimizar, Asegurar, Ejecutar, Proveer).
   - Fórmula lógica: [Verbo en infinitivo] + [la acción técnica real del contrato redactada de forma natural] +
     [con el fin de / para] + [el beneficio directo que obtiene la operación de la ESPY o la prestación de los
     servicios públicos de acueducto, alcantarillado o aseo en el municipio de Yolombó].

2. OBJETIVOS ESPECÍFICOS (El "Cómo técnico" desglosado en 3 a 5 metas):
   - Entre 3 y 5 viñetas, cada una iniciando con un verbo en infinitivo bien escrito (sin cortar letras).
   - Sin trámites administrativos ni frases comodín vacías.
   - Derivados de la materia técnica de la propuesta/cotización o desglose técnico deductivo:
     * Meta 1 (Diagnóstico/Planeación o Abastecimiento): Identificar necesidades en terreno, diagnosticar equipos, organizar rutas o asegurar disponibilidad oportuna de bienes/insumos.
     * Meta 2 (Ejecución Nuclear / Intervención): Acción principal del contrato (reparaciones correctivas, jornadas puerta a puerta, intervención de redes, entrega de químicos).
     * Meta 3 (Calidad / Continuidad Operativa / Mitigación de Riesgos): Funcionamiento seguro de equipos, cumplimiento de normas técnicas/ambientales o reducción de fallas.
     * Meta 4 (Trazabilidad Técnica - Opcional): Documentar técnicamente las intervenciones (historial técnico de equipos, georreferenciación de puntos críticos, censos de usuarios).
"""
import re
from typing import List, Optional, Dict, Any, Tuple
from app.utils.contract_prefix_helper import infer_contract_tipologia
from app.utils.objective_normalizer import (
    clean_technical_text,
    starts_with_infinitive,
    format_single_objective,
    normalize_objetivos_especificos
)
from app.utils.necesidad_builder import (
    _clean_action_from_objeto,
    analyze_objeto_keywords,
    extract_items_from_text,
    _is_valid_item
)

# Frases administrativas y comodines prohibidos como objetivos específicos
PROHIBITED_PATTERNS = [
    r"\binformes?\s+(?:mensual(?:es)?|peri[oó]dic[oa]s?|de\s+actividades|de\s+ejecuci[oó]n|final)\b",
    r"\bcuentas?\s+de\s+cobro\b",
    r"\bseguridad\s+social\b",
    r"\bparafiscal(?:es)?\b",
    r"\bcomit[eé]s?\s+t[eé]cnic[oa]s?\b",
    r"\breunion(?:es)?\b",
    r"\bactas?\s+(?:de\s+inicio|de\s+liquidaci[oó]n|parcial(?:es)?)\b",
    r"\bp[oó]lizas?\b",
    r"\bgurant[ií]as?\b",
    r"\bplazos?\s+fijados?\b",
    r"\bactividades\s+programadas\b",
    r"\ben\s+los\s+tiempos\s+pactados\b",
    r"\bacompañar\s+y\s+asesorar\s+t[eé]cnicamente\s+a\s+la\s+supervisi[oó]n\b",
    r"\bpresentar\s+a\s+la\s+supervisi[oó]n\b"
]


def is_prohibited_objective(text: str) -> bool:
    """Verifica si un objetivo contiene trámites administrativos o frases comodín prohibidas."""
    if not text:
        return True
    t_low = text.lower().strip()
    for pat in PROHIBITED_PATTERNS:
        if re.search(pat, t_low, re.IGNORECASE):
            return True
    return False


def build_objetivo_general(
    objeto: str,
    tipologia: str = "PRESTACION_SERVICIOS",
    contexto: Optional[str] = None,
    nivel_extension: str = "MEDIA",
    instrucciones_adicionales: Optional[str] = None
) -> str:
    """
    Construye el OBJETIVO GENERAL bajo la fórmula obligatoria:
    [Verbo en infinitivo de alto nivel] + [acción técnica real en minúsculas fluida] +
    [para / con el fin de] + [beneficio directo misional de la ESPY en Yolombó].
    
    Queda TERMINANTEMENTE PROHIBIDO concatenar objetos en mayúsculas o fórmulas tipo:
    'Asegurar las labores para PRESTACIÓN DE SERVICIOS DE...'
    """
    nivel = (nivel_extension or "MEDIA").upper().strip()
    clean_act, beneficio_default, _ = analyze_objeto_keywords(objeto, contexto)
    full_text = f"{objeto or ''} {contexto or ''}".lower()
    if instrucciones_adicionales:
        full_text += f" {instrucciones_adicionales.lower()}"

    det_tipo, _ = infer_contract_tipologia(
        propuesta_text=full_text,
        cdp_text=contexto or "",
        current_tipologia=tipologia
    )
    tipo = (det_tipo or tipologia or "PRESTACION_SERVICIOS").upper()

    # Selección de verbo en infinitivo de alto nivel (Implementar, Garantizar, Fortalecer, Optimizar, Asegurar, Ejecutar, Proveer)
    has_gps = bool(re.search(r"\b(?:gps|monitoreo|rastreo|telemetr|geocerca|c[aá]maras?\s+vehicular|adas|dms)\b", full_text))
    if has_gps:
        verbo_alto = "Implementar"
    elif any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"]):
        verbo_alto = "Proveer"
    elif "OBRA" in tipo:
        verbo_alto = "Ejecutar"
    elif any(k in full_text for k in ["mantenimiento", "reparación", "reparacion", "adecuación", "adecuacion", "herramientas"]):
        verbo_alto = "Optimizar"
    elif any(k in full_text for k in ["pgirs", "aseo", "residuos", "ambiental", "capacitacion"]):
        verbo_alto = "Fortalecer"
    elif any(k in full_text for k in ["potabiliz", "acueducto", "agua", "alcantarillado", "redes"]):
        verbo_alto = "Garantizar"
    else:
        verbo_alto = "Asegurar"

    # Preparar acción técnica limpia en minúsculas respetando siglas
    clean_txt = re.sub(
        r"^(?:prestar\s+servicios\s+profesionales\s+y\s+de\s+apoyo\s+a\s+la\s+gesti[oó]n\s+(?:t[eé]cnica\s+)?especializada\s+(?:con\s+plena\s+autonom[ií]a\s+)?(?:para\s+)?|"
        r"suministro,?\s*transporte\s+y\s+entrega\s+a\s+entera\s+satisfacci[oó]n\s+de\s+|"
        r"ejecutar\s+las\s+obras\s+civiles\s+y\s+t[eé]cnicas\s+para\s+|"
        r"arrendamiento\s+de\s+bien\s+inmueble\s+para\s+)\s*",
        "",
        objeto,
        flags=re.IGNORECASE
    ).strip()
    clean_txt = re.sub(r"\s+en\s+la\s+empresa\s+de\s+servicios\s+p[uú]blicos.*$", "", clean_txt, flags=re.IGNORECASE).strip()
    clean_txt = re.sub(r"\s+para\s+la\s+operaci[oó]n\s+t[eé]cnica\s+de\s+la\s+empresa.*$", "", clean_txt, flags=re.IGNORECASE).strip()
    clean_txt = re.sub(r"\s+en\s+la\s+infraestructura\s+de\s+la\s+empresa.*$", "", clean_txt, flags=re.IGNORECASE).strip()

    # Purgar nombres comerciales o errores de OCR en cotizaciones (ej. 'plan r+yplan devideo vavanced')
    if has_gps:
        clean_txt = "el sistema de rastreo satelital GPS, videovigilancia vehicular inteligente ADAS/DMS y monitoreo 24/7 en plataforma para el parque automotor de la ESPY"

    accion_limpia = _clean_action_from_objeto(clean_txt or objeto).strip()

    # Si viene con artículo al inicio ("el mantenimiento de..."), integrarlo directamente
    if re.match(r"^(?:el|la|los|las)\s+", accion_limpia, re.IGNORECASE):
        frase_accion = accion_limpia[0].lower() + accion_limpia[1:]
    elif re.match(r"^(?:realizar|ejecutar|suministrar|prestar|implementar|desarrollar)\s+", accion_limpia, re.IGNORECASE):
        sub_act = re.sub(r"^(?:realizar|ejecutar|prestar|implementar|desarrollar)\s+(?:el|la|los|las)?\s*", "", accion_limpia, flags=re.IGNORECASE).strip()
        frase_accion = f"las actividades técnicas correspondientes a {sub_act}"
    else:
        frase_accion = f"las labores técnicas y operativas de {accion_limpia}"

    # Beneficio directo para la operación de la ESPY o servicios públicos en Yolombó
    if has_gps:
        beneficio_misional = (
            "fortalecer el control de rutas operativas, la seguridad vial (PESV), la custodia patrimonial de la flota "
            "y la prestación eficiente de los servicios públicos en el municipio de Yolombó"
        )
    elif any(k in full_text for k in ["herramienta", "electromec", "equipo", "maquinaria", "taller"]):
        beneficio_misional = (
            "garantizar la disponibilidad, confiabilidad y seguridad técnica de los equipos requeridos en la atención "
            "oportuna de contingencias operativas y el mantenimiento de la infraestructura de acueducto, alcantarillado "
            "y aseo en el municipio de Yolombó"
        )
    elif any(k in full_text for k in ["vehículo", "vehiculo", "transporte", "volqueta"]):
        beneficio_misional = (
            "asegurar la movilidad continua del personal técnico, el transporte oportuno de materiales y la capacidad "
            "de respuesta operativa ante contingencias en los servicios públicos del municipio de Yolombó"
        )
    elif any(k in full_text for k in ["pgirs", "residuos", "aseo", "barrido", "reciclaje"]):
        beneficio_misional = (
            "fortalecer la salubridad pública, el aprovechamiento sostenible de residuos y el cumplimiento de las metas del "
            "Plan de Gestión Integral de Residuos Sólidos (PGIRS) en beneficio de la comunidad del municipio de Yolombó"
        )
    elif any(k in full_text for k in ["médic", "medic", "salud ocupacional", "sg-sst"]):
        beneficio_misional = (
            "preservar la aptitud psicofísica y seguridad del talento humano de la empresa, previniendo accidentes y "
            "enfermedades laborales en la prestación continua de los servicios públicos domiciliarios"
        )
    elif any(k in full_text for k in ["acueducto", "agua potable", "ptap", "potabiliz"]):
        beneficio_misional = (
            "asegurar el suministro continuo, regular y con altos estándares de calidad del agua potable para la "
            "comunidad del municipio de Yolombó"
        )
    elif any(k in full_text for k in ["alcantarillado", "aguas residual", "ptar", "saneamiento"]):
        beneficio_misional = (
            "optimizar la recolección y transporte de aguas residuales domésticas, previniendo reboses y mitigando "
            "riesgos ambientales y sanitarios en el municipio de Yolombó"
        )
    elif any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA"]):
        beneficio_misional = (
            "garantizar el abastecimiento técnico y la continuidad operativa ininterrumpida de los procesos misionales "
            "de la Empresa de Servicios Públicos de Yolombó (ESPY)"
        )
    else:
        beneficio_misional = (
            "optimizar la gestión institucional y asegurar la eficiencia y oportunidad en la prestación de los "
            "servicios públicos domiciliarios a cargo de la ESPY en el municipio de Yolombó"
        )

    if nivel == "CORTA":
        # Conciso (35-45 palabras)
        obj_gen = f"{verbo_alto} {frase_accion}, con el fin de {beneficio_misional}."
    elif nivel == "COMPLETA":
        # Amplio y detallado (70-100 palabras)
        adic_clause = f" atendiendo estrictamente la instrucción de {instrucciones_adicionales.strip()}," if instrucciones_adicionales else ""
        obj_gen = (
            f"{verbo_alto} integralmente {frase_accion}{adic_clause} bajo los más rigurosos estándares técnicos, de calidad, "
            f"seguridad industrial y sostenibilidad ambiental, con el fin de {beneficio_misional}, asegurando el cumplimiento "
            f"permanente de los principios constitucionales de eficacia y continuidad en los servicios públicos del municipio."
        )
    else:
        # MEDIA (Estándar existente)
        obj_gen = f"{verbo_alto} {frase_accion}, con el fin de {beneficio_misional}."

    obj_gen = re.sub(r"\s+", " ", obj_gen).strip()
    # Preservar siempre en mayúsculas las siglas tecnológicas y en minúscula la prestación
    obj_gen = re.sub(r"\bgps\b", "GPS", obj_gen, flags=re.IGNORECASE)
    obj_gen = re.sub(r"\badas/dms\b", "ADAS/DMS", obj_gen, flags=re.IGNORECASE)
    obj_gen = re.sub(r"\badas\b", "ADAS", obj_gen, flags=re.IGNORECASE)
    obj_gen = re.sub(r"\bdms\b", "DMS", obj_gen, flags=re.IGNORECASE)
    obj_gen = re.sub(r"\bla\s+Prestaci[oó]n\b", "la prestación", obj_gen)
    return obj_gen


def build_objetivos_especificos(
    objeto: str,
    tipologia: str = "PRESTACION_SERVICIOS",
    items_propuesta: Optional[List[str]] = None,
    contexto: Optional[str] = None,
    nivel_extension: str = "MEDIA",
    instrucciones_adicionales: Optional[str] = None,
    propuesta_items: Optional[List[str]] = None,
    **kwargs
) -> List[str]:
    """
    Construye OBJETIVOS ESPECÍFICOS técnicos concretos según el nivel de extensión:
    - CORTA: 3 Objetivos Específicos directos (1. Alistamiento/Abastecimiento, 2. Ejecución técnica nuclear, 3. Entrega y calidad).
    - MEDIA: 4 Objetivos Específicos equilibrados (Diagnóstico, Ejecución nuclear, Calidad/Continuidad, Trazabilidad técnica).
    - COMPLETA: 5 a 6 Objetivos Específicos de alta profundidad técnica desglosando fases e impacto verificable.
    """
    raw_prop_items = propuesta_items if propuesta_items is not None else items_propuesta
    nivel = (nivel_extension or "MEDIA").upper().strip()
    full_text = f"{objeto or ''} {contexto or ''}".lower()
    if instrucciones_adicionales:
        full_text += f" {instrucciones_adicionales.lower()}"

    det_tipo, _ = infer_contract_tipologia(
        propuesta_text=full_text,
        cdp_text=contexto or "",
        current_tipologia=tipologia
    )
    tipo = (det_tipo or tipologia or "PRESTACION_SERVICIOS").upper()
    is_suministro = any(k in tipo for k in ["SUMINISTRO", "COMPRAVENTA", "BIENES"])
    is_obra = "OBRA" in tipo

    # 1. Analizar si vienen ítems de la propuesta o cotización
    raw_candidates = list(raw_prop_items or [])
    if not raw_candidates and contexto:
        raw_candidates = extract_items_from_text(contexto)
    
    valid_items = [
        it for it in raw_candidates 
        if _is_valid_item(it) and not is_prohibited_objective(it)
    ]

    objetivos: List[str] = []

    # 2. Generar objetivos específicos estructurados por dominio técnico
    if any(k in full_text for k in ["gps", "monitoreo", "rastreo", "telemetr", "geocerca", "cámara vehicular", "camara vehicular", "video vehicular"]):
        objetivos = [
            "Suministrar e instalar técnicamente las unidades de rastreo satelital GPS LC y periféricos de control y seguridad en el parque automotor de la entidad.",
            "Dotar y configurar las unidades de video vehicular JC371 con cámara frontal ADAS, cámaras internas CI05F Cabin-View DMS y memorias de almacenamiento MicroSD.",
            "Habilitar y garantizar la operatividad de la plataforma web y aplicación móvil de monitoreo 24/7 con control telemétrico de rutas, geocercas y paradas.",
            "Implementar los controles del Plan Estratégico de Seguridad Vial (PESV), identificación electrónica de conductores, capacitación al personal y soporte técnico continuo."
        ]
    elif any(k in full_text for k in ["herramienta", "electromec", "equipo", "maquinaria", "motor", "bomba", "planta", "taller"]):
        objetivos = [
            "Diagnosticar el estado electromecánico inicial, nivel de aislamiento y grado de desgaste técnico de los equipos y herramientas de campo de la entidad.",
            "Ejecutar los mantenimientos preventivos y reparaciones correctivas especializadas con suministro e instalación de repuestos originales a todo costo.",
            "Realizar pruebas de aislamiento dieléctrico, torque y funcionamiento técnico bajo carga para asegurar la operatividad y rendimiento seguro de cada equipo.",
            "Consolidar la trazabilidad técnica e historial de intervenciones por equipo para fortalecer la planeación del mantenimiento en la ESPY.",
            "Certificar la entrega técnica a satisfacción de las herramientas intervenidas con la garantía técnica de los repuestos instalados.",
            "Verificar la disponibilidad operacional inmediata de las cuadrillas mediante el equipamiento en óptimas condiciones de seguridad laboral."
        ]
    elif any(k in full_text for k in ["vehículo", "vehiculo", "transporte", "volqueta", "camion"]):
        objetivos = [
            "Efectuar la inspección técnico-mecánica preoperacional y verificación del estado físico y documental del parque automotor asignado.",
            "Garantizar la disponibilidad mecánica y operativa continua del automotor para el traslado eficiente de cuadrillas y materiales en el municipio.",
            "Ejecutar los mantenimientos preventivos y reposición de consumibles requeridos para mitigar parálisis operativas en la atención de emergencias.",
            "Registrar el control de kilometraje, rutas de operación y horas de servicio para optimizar la logística de transporte de la ESPY.",
            "Acreditar el mantenimiento vigente de las pólizas de aseguramiento, revisión técnico-mecánica y permisos de circulación.",
            "Garantizar la continuidad en la prestación de los servicios públicos mediante el soporte logístico vehicular oportuno."
        ]
    elif any(k in full_text for k in ["pgirs", "residuos", "aseo", "barrido", "reciclaje", "arbolado", "poda"]):
        objetivos = [
            "Identificar y caracterizar los puntos críticos de acumulación de residuos y sectores prioritarios de intervención en el municipio de Yolombó.",
            "Ejecutar las jornadas técnicas de sensibilización ciudadana, separación en la fuente y actividades operativas de aprovechamiento conforme al PGIRS.",
            "Verificar la adopción de buenas prácticas ambientales y reducción de residuos dispuestos para mejorar los indicadores de sostenibilidad municipal.",
            "Consolidar la georreferenciación de puntos atendidos y el censo de usuarios sensibilizados para el seguimiento y evaluación del PGIRS por parte de la ESPY.",
            "Implementar talleres pedagógicos con comunidades e instituciones educativas para fomentar la cultura de reciclaje y aseo urbano.",
            "Evaluar el impacto ambiental y cuantitativo de las metas alcanzadas en la gestión integral de residuos sólidos en el municipio."
        ]
    elif any(k in full_text for k in ["médic", "medic", "salud ocupacional", "sg-sst", "osteomuscular", "visiometr"]):
        objetivos = [
            "Planear y coordinar la logística médica para la práctica in situ de valoraciones ocupacionales y paraclínicos a los trabajadores de la empresa.",
            "Practicar los exámenes médicos periódicos, de ingreso o egreso y pruebas de laboratorio clínico conforme a los profesiogramas establecidos.",
            "Emitir los certificados de aptitud psicofísica laboral con recomendaciones preventivas individuales orientadas a mitigar enfermedades profesionales.",
            "Consolidar el diagnóstico epidemiológico de salud del personal de la ESPY para orientar las intervenciones prioritarias del SG-SST.",
            "Estructurar recomendaciones ergonómicas y preventivas por puesto de trabajo para reducir la tasa de siniestralidad y ausentismo laboral."
        ]
    elif is_obra or any(k in full_text for k in ["tubería", "tuberia", "alcantarillado", "acueducto", "pavimento", "excavaci"]):
        if len(valid_items) >= 3:
            obj1 = format_single_objective(f"Realizar el replanteo topográfico y excavaciones iniciales requeridas para {valid_items[0]}")
            obj2 = format_single_objective(valid_items[1] if len(valid_items) > 1 else "Instalar las tuberías y accesorios hidrosanitarios")
            obj3 = format_single_objective(valid_items[2] if len(valid_items) > 2 else "Efectuar las pruebas hidrostáticas de presión y estanqueidad")
            obj4 = format_single_objective(f"Ejecutar los llenos compactados y reposición final de pavimentos para restablecer el entorno intervenido")
            obj5 = format_single_objective("Levantar las actas de medición técnica de cantidades ejecutadas y planos récord de obra")
            obj6 = format_single_objective("Garantizar la estabilidad y calidad de las obras civiles ejecutadas conforme a las normas técnicas")
            objetivos = [obj1, obj2, obj3, obj4, obj5, obj6]
        else:
            objetivos = [
                "Realizar el diagnóstico topográfico y levantamiento técnico del trazado de redes a intervenir en el municipio.",
                "Ejecutar las actividades constructivas de excavación, instalación de tuberías y accesorios conforme al Reglamento RAS.",
                "Efectuar pruebas hidrostáticas de presión y desinfección técnica para garantizar la estanqueidad y calidad de las conducciones.",
                "Levantar los planos récord y registro dimensional de la infraestructura instalada para la actualización del catastro de redes de la ESPY.",
                "Restablecer las condiciones de transitabilidad urbana mediante la reposición técnica de pavimentos y espacio público intervenido.",
                "Asegurar la estabilidad y durabilidad de las obras ejecutadas mediante estrictos controles de calidad de materiales."
            ]
    elif any(k in full_text for k in ["papelería", "papeleria", "útiles", "utiles", "insumos de oficina"]):
        objetivos = [
            "Coordinar el alistamiento y verificación de referencias conforme a los requerimientos de insumos de las diferentes áreas de la entidad.",
            "Suministrar y entregar físicamente en el Almacén General los bienes y papelería cumpliendo especificaciones de primera calidad.",
            "Garantizar la disponibilidad oportuna de útiles de oficina para evitar retrasos en la gestión administrativa y atención de usuarios.",
            "Legalizar las entregas materiales con remisiones detalladas e inventario para el control de existencias en el Almacén de la ESPY.",
            "Reponer de forma prioritaria cualquier elemento o insumo que presente defectos de fabricación o embalaje."
        ]
    elif is_suministro:
        objetivos = [
            "Asegurar la disponibilidad, embalaje y alistamiento oportuno de los bienes conforme a las fichas técnicas solicitadas.",
            "Suministrar y transportar bajo modalidad DDP la totalidad de los materiales al Almacén General de la empresa.",
            "Verificar las especificaciones de calidad, rotulado y certificaciones técnicas de fábrica para garantizar la vida útil de los elementos.",
            "Legalizar formalmente el ingreso al inventario institucional mediante acta de entrada a satisfacción conjunta con el supervisor.",
            "Garantizar la reposición inmediata de insumos o materiales que presenten averías o faltantes durante el descargue.",
            "Suministrar los certificados de calidad y fichas de seguridad técnica correspondientes a cada lote entregado."
        ]
    elif any(k in full_text for k in ["jur[ií]dic", "abogad", "legal", "asesor[ií]a", "contractual"]):
        objetivos = [
            "Revisar y estructurar jurídicamente los procesos de contratación y actos administrativos requeridos por la ESPY bajo la Ley 142 de 1994.",
            "Prestar asesoría técnica y legal oportuna en la elaboración de estudios previos, minutas y respuestas a solicitudes institucionales.",
            "Blindar jurídicamente las actuaciones corporativas de la empresa mitigando contingencias litigiosas o sancionatorias ante entes de control.",
            "Consolidar el seguimiento normativo y archivo digital de expedientes contractuales para el control y transparencia administrativa de la ESPY.",
            "Acompañar jurídicamente los comités de contratación y etapas de liquidación de los acuerdos negociales de la entidad."
        ]
    elif any(k in full_text for k in ["contab", "financier", "tributar", "presupuesto"]):
        objetivos = [
            "Revisar y procesar oportunamente los soportes contables, conciliaciones bancarias y registros financieros de la entidad.",
            "Estructurar los informes financieros y liquidaciones tributarias conforme a los marcos normativos aplicables a las ESP.",
            "Asegurar la veracidad, oportunidad y razonabilidad de la información contable para la toma de decisiones estratégicas de la gerencia.",
            "Organizar los archivos y soportes tributarios para la atención oportuna de requerimientos de la DIAN y entes de vigilancia.",
            "Efectuar el control de consistencia entre los registros contables y la ejecución presupuestal de los contratos de la empresa."
        ]
    else:
        action_clean = _clean_action_from_objeto(objeto)
        objetivos = [
            f"Diagnosticar las necesidades operativas y definir el plan técnico de trabajo para {action_clean}.",
            f"Ejecutar de forma oportuna y especializada las actividades técnicas requeridas para {action_clean}.",
            f"Asegurar el cumplimiento de los estándares de calidad y seguridad operativa en el desarrollo del servicio.",
            f"Documentar técnicamente los avances y resultados alcanzados para retroalimentar la planeación institucional de la ESPY.",
            f"Verificar el estricto cumplimiento de las metas y cronograma concertado con la supervisión contractual.",
            f"Consolidar la entrega formal y cierre técnico de las actividades desarrolladas en beneficio de la entidad."
        ]

    # Limpieza e infinitivos
    cleaned_result: List[str] = []
    seen = set()
    for ob in objetivos:
        clean_ob = clean_technical_text(ob)
        if not clean_ob or is_prohibited_objective(clean_ob):
            continue
        formatted_ob = format_single_objective(clean_ob)
        key = formatted_ob.lower().rstrip(".")
        if key not in seen and len(formatted_ob) >= 15:
            seen.add(key)
            cleaned_result.append(formatted_ob)

    # Determinar cantidad exacta según el nivel solicitado
    if nivel == "CORTA":
        # 3 Objetivos Específicos directos
        target_count = 3
    elif nivel == "COMPLETA":
        # 5 a 6 Objetivos Específicos
        target_count = 6
    else:
        # MEDIA: 4 Objetivos Específicos
        target_count = 4

    # Garantizar que alcancemos target_count si faltan
    if len(cleaned_result) < target_count:
        action_clean = _clean_action_from_objeto(objeto)
        extras = [
            format_single_objective(f"Identificar los requerimientos específicos y coordinar la logística operativa de {action_clean}"),
            format_single_objective(f"Ejecutar las labores técnicas y operativas necesarias para {action_clean}"),
            format_single_objective(f"Verificar la calidad y funcionamiento técnico de las actividades desarrolladas en beneficio de la ESPY"),
            format_single_objective(f"Documentar y entregar los informes y soportes técnicos de las intervenciones realizadas"),
            format_single_objective(f"Asegurar la continuidad técnica y mitigación de fallas en los procesos de la empresa"),
            format_single_objective(f"Garantizar el cumplimiento de las directrices y estándares institucionales de la ESPY")
        ]
        for ex in extras:
            if ex.lower().rstrip(".") not in seen and len(cleaned_result) < target_count:
                cleaned_result.append(ex)
                seen.add(ex.lower().rstrip("."))

    return cleaned_result[:target_count]


def build_objetivos_contrato(
    objeto: str,
    tipologia: str = "PRESTACION_SERVICIOS",
    items_propuesta: Optional[List[str]] = None,
    contexto: Optional[str] = None,
    nivel_extension: str = "MEDIA",
    instrucciones_adicionales: Optional[str] = None,
    propuesta_items: Optional[List[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Retorna tanto el OBJETIVO GENERAL como los OBJETIVOS ESPECÍFICOS formateados y validados,
    garantizando coherencia total con la Descripción de la Necesidad y las Obligaciones.
    """
    effective_items = propuesta_items if propuesta_items is not None else items_propuesta
    ctx_full = f"{objeto or ''} {contexto or ''}".lower()
    det_tipo, _ = infer_contract_tipologia(
        propuesta_text=ctx_full,
        cdp_text=contexto or "",
        current_tipologia=tipologia
    )
    effective_tipologia = det_tipo or tipologia or "PRESTACION_SERVICIOS"

    obj_general = build_objetivo_general(
        objeto=objeto, 
        tipologia=effective_tipologia, 
        contexto=contexto,
        nivel_extension=nivel_extension,
        instrucciones_adicionales=instrucciones_adicionales
    )
    obj_especificos = build_objetivos_especificos(
        objeto=objeto, 
        tipologia=effective_tipologia, 
        items_propuesta=effective_items, 
        contexto=contexto,
        nivel_extension=nivel_extension,
        instrucciones_adicionales=instrucciones_adicionales
    )

    return {
        "objetivo_general": obj_general,
        "objetivos_especificos": obj_especificos,
        "total_especificos": len(obj_especificos)
    }
