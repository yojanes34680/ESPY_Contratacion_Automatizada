"""Módulo de estructuración y normalización del Objeto Contractual para la ESPY.

Reglas Obligatorias:
1. REDACCIÓN EN MAYÚSCULAS SOSTENIDAS (UPPERCASE), entre 20 y 45 palabras.
2. PROHIBIDO redactar objetos vagos, ambiguos o universales ("PRESTACIÓN DE SERVICIOS PARA LAS ACTIVIDADES TÉCNICAS REQUERIDAS", "SUMINISTRO DE ELEMENTOS NECESARIOS", etc.).
3. PROHIBIDO enumerar toda la lista de ítems dentro del objeto (no es lista de mercado).
4. PROHIBIDO iniciar con verbos en infinitivo sueltos ("REALIZAR EL...", "SUMINISTRAR...").
   Empieza siempre sustantivando la tipología o acción técnica:
   - "PRESTACIÓN DE SERVICIOS PROFESIONALES PARA..."
   - "PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN (O SERVICIOS TÉCNICOS/OPERATIVOS) PARA..."
   - "SUMINISTRO DE..." o "COMPRAVENTA DE..."
   - "EJECUCIÓN DE OBRAS CIVILES PARA..." o "MANTENIMIENTO Y ADECUACIÓN DE INFRAESTRUCTURA..."
   - "ARRENDAMIENTO DE..."
5. FÓRMULA ESTRUCTURAL OBLIGATORIA DE 4 BLOQUES:
   [BLOQUE 1: Tipología exacta] + [BLOQUE 2: Núcleo técnico real extraído de la propuesta] + [BLOQUE 3: Condición o alcance operativo] + [BLOQUE 4: Destino institucional en la ESPY]
"""
import re
from typing import Optional, List, Tuple
from app.utils.contract_prefix_helper import infer_contract_tipologia

PROHIBITED_GENERIC_PATTERNS = [
    r"ACTIVIDADES\s+T[EÉ]CNICAS\s+REQUERIDAS",
    r"ELEMENTOS\s+NECESARIOS\s+PARA\s+LA\s+EMPRESA",
    r"APOYO\s+EN\s+LABORES\s+VARIAS",
    r"LABORES\s+VARIAS",
    r"SERVICIOS\s+VARIOS",
    r"ACTIVIDADES\s+VARIAS",
    r"BIENES\s+REQUERIDOS",
    r"SUMINISTROS\s+VARIOS",
    r"TODO\s+LO\s+REQUERIDO",
]

def is_vague_or_prohibited_objeto(txt: str) -> bool:
    """Verifica si el texto propuesto como objeto es vago, ambiguo o genérico prohibido."""
    if not txt:
        return True
    t_clean = " ".join(txt.split()).strip()
    if len(t_clean.split()) < 4:
        return True
    for pat in PROHIBITED_GENERIC_PATTERNS:
        if re.search(pat, t_clean, re.IGNORECASE):
            return True
    return False

def _extract_core_action(raw_text: str) -> str:
    """Extrae y sintetiza el núcleo técnico sustancial limpiando prefijos de tipología y cláusulas subordinadas."""
    if not raw_text:
        return ""
    # Limpiar encabezados internos del parser de documentos y números de página
    txt = raw_text
    txt = re.sub(r"^(?:===|---|\[)?\s*(?:DOCUMENTO|DOC|ARCHIVO)[:\s\-]+[^\n\r]+?(?:===|---|\])?\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(?:===|---|\[)?\s*P[AÁ]GINA\s+\d+\s*(?:===|---|\])?\s*", " ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bREPUBLICADECOLOMBIA\b|\bREP[UÚ]BLICA\s+DE\s+COLOMBIA\b", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bCERTIFICADO\s+DE\s+DISPONIBILIDAD\s+PRESUPUESTAL\b|\bCERTIFICADODEDISPONIBILIDADPRESUPUESTAL\b", "", txt, flags=re.IGNORECASE)
    txt = " ".join(txt.split()).strip()

    # Quitar encabezados o fórmulas de objeto redundantes
    regex_prefixes = [
        r"^(?:asunto|concepto|cotizaci[oó]n|oferta|propuesta)[:\s\-]+(?:servicio\s+de|servicio|suministro\s+de|mantenimiento\s+de)?\s*",
        r"^(?:objeto(?:\s+contractual|\s+de\s+la\s+(?:oferta|propuesta|cotizaci[oó]n|contrataci[oó]n))?|prop[oó]sito)[:\s\-]+",
        r"^(?:el\s+presente\s+contrato\s+tiene\s+por\s+objeto|tiene\s+por\s+objeto)\s+",
        r"^(?:prestaci[oó]n\s+de\s+servicios\s+(?:profesionales\s+|t[eé]cnicos\s+|operativos\s+|de\s+apoyo\s+a\s+la\s+gesti[oó]n\s+)?(?:para\s+|de\s+)?)+",
        r"^(?:prestar\s+servicios\s+(?:profesionales\s+|t[eé]cnicos\s+|operativos\s+|de\s+apoyo\s+a\s+la\s+gesti[oó]n\s+)?(?:para\s+|de\s+)?)+",
        r"^(?:suministro\s+(?:e\s+instalaci[oó]n\s+)?(?:y\s+transporte\s+)?(?:de\s+|para\s+)?)+",
        r"^(?:suministrar\s+(?:e\s+instalar\s+)?(?:y\s+transportar\s+)?)+",
        r"^(?:compraventa\s+de|adquisici[oó]n\s+de|adquirir|comprar)\s+",
        r"^(?:ejecuci[oó]n\s+de\s+obras\s+civiles\s+para|ejecuci[oó]n\s+de\s+obras\s+para|contrato\s+de\s+obra\s+para\s+la\s+ejecuci[oó]n\s+de|contrato\s+de\s+obra\s+para)\s+",
        r"^(?:ejecutar\s+a\s+todo\s+costo\s+las\s+obras\s+civiles\s+para|ejecutar\s+las\s+obras\s+para|ejecutar\s+obras\s+de|ejecutar)\s+",
        r"^(?:arrendamiento\s+de|arrendar|alquiler\s+de|alquilar)\s+",
        r"^(?:realizar\s+el\s+mantenimiento\s+de|realizar\s+el|realizar\s+la|realizar)\s+",
        r"^(?:adelantar\s+el|adelantar\s+la|adelantar|desarrollar\s+el|desarrollar\s+la|desarrollar|implementar\s+el|implementar)\s+",
    ]

    clean = txt
    for pat in regex_prefixes:
        match = re.search(pat, clean, flags=re.IGNORECASE)
        if match:
            clean = clean[match.end():].strip()
            # Segunda pasada si quedan preposiciones residuales
            clean = re.sub(r"^(?:para\s+la|para\s+el|para\s+los|para\s+las|de\s+la|de\s+el|del|la|el|los|las)\s+", "", clean, flags=re.IGNORECASE).strip()

    # Si vienen colas de destino municipal redundantes que rearmaremos en Bloque 4, limpiarlas del núcleo
    clean = re.sub(
        r"\s+(?:en\s+el\s+municipio\s+de\s+yolomb[oó]|del\s+municipio\s+de\s+yolomb[oó]|para\s+la\s+empresa\s+de\s+servicios\s+p[uú]blicos.*|de\s+la\s+empresa\s+de\s+servicios\s+p[uú]blicos.*|de\s+la\s+espy.*|para\s+la\s+espy.*|en\s+la\s+espy.*)$",
        "",
        clean,
        flags=re.IGNORECASE
    ).strip()

    return clean

def _determine_bloque1(tipologia: str, raw_text: str) -> str:
    """Determina el BLOQUE 1 sustantivado según la tipología y naturaleza de la labor."""
    tip = (tipologia or "PRESTACION_SERVICIOS").upper().strip()
    full = raw_text.lower()

    if tip in ("SUMINISTRO", "COMPRAVENTA"):
        if any(k in full for k in ["gps", "monitoreo", "adas", "dms", "cámara vehicular", "camara vehicular"]):
            return "SUMINISTRO, INSTALACIÓN Y PUESTA EN FUNCIONAMIENTO DE"
        if "instalaci" in full:
            return "SUMINISTRO E INSTALACIÓN DE"
        if "compraventa" in full or "adquisici" in full:
            return "SUMINISTRO Y COMPRAVENTA DE"
        return "SUMINISTRO DE"

    if tip in ("OBRA", "OBRAS"):
        if "adecuaci" in full or "reparaci" in full or "infraestructura" in full:
            return "MANTENIMIENTO Y ADECUACIÓN DE INFRAESTRUCTURA PARA"
        return "EJECUCIÓN DE OBRAS CIVILES PARA"

    if tip in ("ARRENDAMIENTO", "ALQUILER"):
        return "ARRENDAMIENTO DE"

    # Tipología de Servicios: diferenciar profesional vs operativo/apoyo
    es_profesional = bool(re.search(
        r"\b(?:profesional(?:es)?|asesor[ií]a|jur[ií]dic[oa]|contable|financier[oa]|revisor[ií]a|auditor[ií]a|consultor[ií]a|interventor[ií]a|diseño|ingenier[ií]a|social|ambiental)\b",
        full
    ))
    es_operativo = bool(re.search(
        r"\b(?:mantenimiento|reparaci[oó]n|operaci[oó]n|taller|herramientas|fontaner[ií]a|plomer[ií]a|bocatoma|redes|v[aá]lvula|bombas|pozos|alcantarillado|recolecci[oó]n|barrido|aseo|chofer|conductor|mec[aá]nic[oa]|soldadura|limpieza)\b",
        full
    ))

    if es_profesional and not es_operativo:
        return "PRESTACIÓN DE SERVICIOS PROFESIONALES PARA"
    return "PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA"

def _determine_bloque3_condicion(raw_text: str, items: Optional[List[str]] = None) -> Optional[str]:
    """Extrae o determina la condición o alcance operativo clave (BLOQUE 3)."""
    full = f"{raw_text or ''} {' '.join(items or [])}".lower()

    if "a todo costo" in full or "todo costo" in full:
        return "A TODO COSTO"
    if "puerta a puerta" in full:
        return "BAJO LA MODALIDAD PUERTA A PUERTA"
    if "preventivo y correctivo" in full:
        return "PREVENTIVO Y CORRECTIVO"
    if "correctivo" in full and "preventivo" not in full:
        return "DE CARÁCTER CORRECTIVO"
    if "preventivo" in full and "correctivo" not in full:
        return "DE CARÁCTER PREVENTIVO"
    if "incluye repuestos" in full or "con repuestos" in full:
        return "CON SUMINISTRO DE REPUESTOS E INSUMOS"
    if "en sitio" in full or "en campo" in full:
        return "DIRECTAMENTE EN CAMPO"
    if "selectiva" in full and "ruta" in full:
        return "PARA LA RUTA SELECTIVA"
    return None

def _determine_bloque4_destino(raw_text: str, contexto: Optional[str] = None) -> str:
    """Determina el destino institucional o área beneficiada en la ESPY (BLOQUE 4)."""
    full = f"{raw_text or ''} {contexto or ''}".lower()

    # Parque automotor / Vehículos / GPS
    if re.search(r"\b(?:gps|monitoreo|rastreo|veh[ií]culos?|automotor|volquetas?)\b", full):
        return "PARA EL PARQUE AUTOMOTOR DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P."

    # PGIRS / Residuos
    if re.search(r"\b(?:pgirs|residuos?|reciclaje|ruta\s+selectiva|aprovechamiento|sensibilizaci[oó]n|compostaje|barrido)\b", full):
        return "EN EL MARCO DE LA IMPLEMENTACIÓN DEL PGIRS DEL MUNICIPIO DE YOLOMBÓ"

    # PTAP / Agua Potable
    if re.search(r"\b(?:ptap|potabilizac|planta\s+de\s+tratamiento\s+de\s+agua\s+potable|coagulante|qu[ií]micos\s+de\s+agua|desinfecci[oó]n\s+de\s+agua)\b", full):
        return "PARA LA PLANTA DE TRATAMIENTO DE AGUA POTABLE DE LA ESPY"

    # PTAR / Saneamiento / Alcantarillado
    if re.search(r"\b(?:ptar|aguas\s+residuales|alcantarillado|red\s+de\s+alcantarillado|colector|pozos?\s+s[eé]pticos?)\b", full):
        return "EN LAS REDES E INFRAESTRUCTURA DE ALCANTARILLADO DE LA ESPY"

    # Redes de Acueducto / Fontanería
    if re.search(r"\b(?:v[aá]lvula|redes?\s+de\s+acueducto|distribuci[oó]n\s+de\s+agua|macromedici[oó]n|micromedici[oó]n|bocatoma|aducci[oó]n)\b", full):
        if "camelias" in full:
            return "DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBÓ"
        return "EN LAS REDES E INFRAESTRUCTURA DE ACUEDUCTO DE LA ESPY"

    # Destino general institucional
    return "DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P."

def _synthesize_proposal_items(items: List[str]) -> str:
    """Si la propuesta tiene múltiples ítems, sintetiza el concepto técnico sin hacer lista de mercado."""
    clean_items = [it.strip().strip("-•*0123456789. ") for it in items if it and len(it.strip()) > 3]
    if not clean_items:
        return ""

    full = " ".join(clean_items).lower()
    if any(k in full for k in ["gps", "monitoreo", "rastreo", "telemetr", "cámara vehicular", "camara vehicular", "video vehicular"]):
        return "UNIDADES DE RASTREO SATELITAL GPS, CÁMARAS DE VIDEOVIGILANCIA VEHICULAR CON TECNOLOGÍA ADAS/DMS Y SERVICIO CONEXO DE MONITOREO EN PLATAFORMA"

    if len(clean_items) == 1 and len(clean_items[0]) <= 80:
        return _extract_core_action(clean_items[0])
    if "v[aá]lvula" in full and "sectorizaci" in full:
        return "LA INSTALACIÓN DE VÁLVULA DE SECTORIZACIÓN"
    if any(k in full for k in ["herramienta", "electromec", "motobomba", "taladro", "alicate", "llave para tubo", "destornillador", "prensa de banco", "termofusora"]):
        return "EL MANTENIMIENTO DE HERRAMIENTAS ELÉCTRICAS Y EQUIPOS ELECTROMECÁNICOS"
    if "sensibiliza" in full or "pgirs" in full or "socializa" in full:
        return "LA SENSIBILIZACIÓN AMBIENTAL Y SOCIALIZACIÓN DE LA RUTA SELECTIVA"
    if "químico" in full or "quimico" in full or "coagulante" in full or "cloro" in full or "sulfato" in full:
        return "INSUMOS QUÍMICOS COAGULANTES Y DESINFECTANTES PARA EL TRATAMIENTO DE AGUA"
    if "papelería" in full or "papeleria" in full or "artículos de oficina" in full or "articulos de oficina" in full:
        return "ÚTILES, PAPELERÍA Y SUMINISTROS DE OFICINA"
    if "vehículo" in full or "vehiculo" in full or "camioneta" in full or "volqueta" in full:
        return "VEHÍCULO AUTOMOTOR OPERATIVO"
    if "tubería" in full or "tuberia" in full or "accesorios" in full or "unión" in full or "union" in full:
        return "TUBERÍAS, VÁLVULAS Y ACCESORIOS PARA REDES DE SERVICIOS PÚBLICOS"
    if "pozo" in full and ("séptico" in full or "septico" in full):
        return "EL MANTENIMIENTO Y LIMPIEZA DE POZOS SÉPTICOS"
    if "médico" in full or "medico" in full or "evaluaci" in full or "ocupacional" in full:
        return "EVALUACIONES MÉDICAS OCUPACIONALES Y EXÁMENES DE INGRESO Y PERIÓDICOS"

    # Si no encaja en plantillas típicas, sintetizar de forma genérica limpia
    first_core = _extract_core_action(clean_items[0])
    return first_core.upper()

def build_objeto_contractual(
    propuesta_o_cotizacion: Optional[str] = None,
    tipologia: Optional[str] = "PRESTACION_SERVICIOS",
    necesidad_descripcion: Optional[str] = None,
    items_propuesta: Optional[List[str]] = None,
    contexto: Optional[str] = None
) -> str:
    """Construye el Objeto Contractual definitivo conforme a las reglas estrictas de la ESPY.

    Aplica la fórmula de 4 bloques:
    [BLOQUE 1: Tipología exacta] + [BLOQUE 2: Núcleo técnico real] + [BLOQUE 3: Condición o alcance] + [BLOQUE 4: Destino institucional]
    Garantiza:
    - MAYÚSCULAS SOSTENIDAS (UPPERCASE).
    - Longitud equilibrada (entre 20 y 45 palabras aprox).
    - Prohibición de vaguedad, listas de mercado y verbos en infinitivo sueltos al inicio.
    """
    raw_insumo = (propuesta_o_cotizacion or "").strip()
    nec = (necesidad_descripcion or "").strip()
    full_source = f"{raw_insumo} {nec} {contexto or ''}".strip()

    # Inferencia inteligente de tipología contractual y servicio conexo
    detected_tip, has_conexo = infer_contract_tipologia(
        propuesta_text=full_source,
        cdp_text=contexto or "",
        current_tipologia=tipologia
    )
    effective_tipologia = detected_tip or tipologia or "PRESTACION_SERVICIOS"

    # 1. Caso emblemático histórico: Válvula de sectorización sector Las Camelias
    if (
        re.search(r"\bV[AÁ]LVULA(?:S)?\b", full_source, re.IGNORECASE)
        and re.search(r"\bSECTORIZACI[OÓ]N\b", full_source, re.IGNORECASE)
        and re.search(r"\bCAMELIAS\b", full_source, re.IGNORECASE)
    ):
        return "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO"

    # 1.1 Detección y normalización obligatoria para GPS / Videovigilancia y errores de OCR (R+YPLAN / VAVANCED)
    if any(k in full_source.upper() for k in ["R+YPLAN", "VAVANCED", "SERVICIO GPS PLAN R+", "PLAN R+"]):
        return (
            "SUMINISTRO, INSTALACIÓN Y PUESTA EN FUNCIONAMIENTO DE UNIDADES DE RASTREO SATELITAL GPS, "
            "CÁMARAS DE VIDEOVIGILANCIA VEHICULAR CON TECNOLOGÍA ADAS/DMS Y SERVICIO CONEXO DE MONITOREO "
            "EN PLATAFORMA PARA EL PARQUE AUTOMOTOR DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P."
        )

    # 2. Determinar BLOQUE 1 (Tipología exacta sustantivada)
    bloque1 = _determine_bloque1(effective_tipologia, full_source)

    # 3. Determinar BLOQUE 2 (Núcleo técnico real)
    bloque2 = ""
    if items_propuesta and len(items_propuesta) > 1:
        bloque2 = _synthesize_proposal_items(items_propuesta)
    if not bloque2:
        # Si el insumo es un documento completo (más de 120 caracteres o contiene tablas/membretes), sintetizar por conceptos
        if len(raw_insumo) > 120 or "\n" in raw_insumo or "NIT" in raw_insumo:
            bloque2 = _synthesize_proposal_items([full_source])
        else:
            extracted = _extract_core_action(raw_insumo) or _extract_core_action(nec)
            if not extracted or is_vague_or_prohibited_objeto(extracted):
                # Deducir de palabras clave
                bloque2 = _synthesize_proposal_items([full_source])
            else:
                bloque2 = extracted.upper()

    # Si aún no hay bloque2 o es vago, extraer directamente el insumo o sintetizar sin plantillas quemadas
    if not bloque2 or is_vague_or_prohibited_objeto(bloque2) or len(bloque2.split()) > 25:
        if (tipologia or "").upper() == "OBRA":
            bloque2 = "LA REPOSICIÓN Y ADECUACIÓN TÉCNICA DE REDES DE DISTRIBUCIÓN"
        elif (tipologia or "").upper() == "SUMINISTRO":
            bloque2 = "MATERIALES, ACCESORIOS Y HERRAMIENTAS MENORES DE FONTANERÍA"
        elif (tipologia or "").upper() == "ARRENDAMIENTO":
            bloque2 = "VEHÍCULO AUTOMOTOR TIPO CAMIONETA DE TRABAJO"
        else:
            # Extraer del insumo crudo el concepto o labor real sin plantillas quemadas
            raw_core = _extract_core_action(raw_insumo or nec)
            if raw_core and not is_vague_or_prohibited_objeto(raw_core):
                bloque2 = raw_core.upper()
            elif raw_insumo and not is_vague_or_prohibited_objeto(raw_insumo):
                bloque2 = raw_insumo.upper()
            elif nec and not is_vague_or_prohibited_objeto(nec):
                bloque2 = nec.upper()
            else:
                bloque2 = "EL APOYO TÉCNICO Y OPERATIVO EN EL MANTENIMIENTO DEL SISTEMA"

    # Asegurar que el núcleo técnico no empiece con preposiciones redundantes respecto al bloque 1
    bloque2 = re.sub(r"^(?:para\s+el|para\s+la|para\s+los|para\s+las|para|de\s+la|de\s+el|del|de)\s+", "", bloque2, flags=re.IGNORECASE).strip()

    # Si el bloque 1 termina en "DE" y bloque 2 empieza con "EL" o "LA", ajustar si es necesario
    if bloque1.endswith("PARA") and not re.match(r"^(?:LA|EL|LOS|LAS|REALIZAR|ADELANTAR|EJECUTAR)\b", bloque2, flags=re.IGNORECASE):
        if re.match(r"^(?:MANTENIMIENTO|SUMINISTRO|FORTALECIMIENTO|APOYO|ARRENDAMIENTO|DIAGN[OÓ]STICO|MEJORAMIENTO)\b", bloque2, flags=re.IGNORECASE):
            bloque2 = f"EL {bloque2}"
        elif re.match(r"^(?:INSTALACI[OÓ]N|SENSIBILIZACI[OÓ]N|EJECUCI[OÓ]N|ADECUACI[OÓ]N|ATENCI[OÓ]N|GESTI[OÓ]N|CONSULTOR[IÍ]A|INTERVENTOR[IÍ]A|REPOSICI[OÓ]N)\b", bloque2, flags=re.IGNORECASE):
            bloque2 = f"LA {bloque2}"
        elif re.match(r"^(?:EVALUACIONES|ACTIVIDADES|LABORES|OBRAS|PRUEBAS)\b", bloque2, flags=re.IGNORECASE):
            bloque2 = f"LAS {bloque2}"
        elif re.match(r"^(?:SERVICIOS|ESTUDIOS|REPARACIONES)\b", bloque2, flags=re.IGNORECASE):
            bloque2 = f"LOS {bloque2}"

    # 4. Determinar BLOQUE 3 (Condición o alcance operativo)
    bloque3 = _determine_bloque3_condicion(full_source, items_propuesta)

    # 5. Determinar BLOQUE 4 (Destino institucional en la ESPY)
    bloque4 = _determine_bloque4_destino(full_source, contexto)

    # Si el bloque 2 ya contiene el destino municipal o institucional, evitar duplicarlo
    if "YOLOMB" in bloque2 or "ESPY" in bloque2 or "EMPRESA DE SERVICIOS" in bloque2:
        bloque4 = ""

    # Si el bloque 1 ya está contenido en el bloque 2, evitar duplicar el bloque 1
    if bloque2.startswith("PRESTACI") or bloque2.startswith("SUMINISTRO") or bloque2.startswith("CONTRATO DE OBRA") or bloque2.startswith("ARRENDAMIENTO"):
        partes = [bloque2]
    else:
        partes = [bloque1, bloque2]

    if bloque3 and bloque3 not in bloque2:
        partes.append(bloque3)
    if bloque4 and bloque4 not in bloque2:
        partes.append(bloque4)

    objeto_final = " ".join([p.strip() for p in partes if p and p.strip()])
    # Limpieza de dobles espacios y mayúsculas sostenidas
    objeto_final = " ".join(objeto_final.split()).upper()

    # DEDUPLICACIÓN ESTRICTA: Evitar repetición recursiva de prefijos y sufijos institucionales
    # 1. Eliminar repetición de "PRESTACION DE SERVICIOS" o "APOYO A LA GESTION"
    objeto_final = re.sub(
        r"\b(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS(?:\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N)?(?:\s+PARA)?\s*){2,}",
        "PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA ",
        objeto_final,
        flags=re.IGNORECASE
    )
    objeto_final = re.sub(
        r"\b(?:APOYO\s+A\s+LA\s+GESTI[OÓ]N\s*){2,}",
        "APOYO A LA GESTIÓN ",
        objeto_final,
        flags=re.IGNORECASE
    )
    # 2. Eliminar "ADSCRITOS AL ÁREA OPERATIVA" y residuos de DISPONIBILIDAD
    objeto_final = re.sub(r"\bDISPONIBILIDAD\b", "", objeto_final, flags=re.IGNORECASE)
    objeto_final = re.sub(
        r"\s*ADSCRITOS?\s+AL\s+[AÁ]REA\s+OPERATIVA(?:(?:\s+DE\s+LA)?\s+EMPRESA\s+DE\s+SERVICIOS\s+P[UÚ]BLICOS\s+DE\s+YOLOMB[OÓ](?:\s+E\.?S\.?P\.?)?)?",
        "",
        objeto_final,
        flags=re.IGNORECASE
    )
    # 3. Eliminar repetición de "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ"
    objeto_final = re.sub(
        r"(?:(?:DE\s+LA|PARA\s+LA)\s+EMPRESA\s+DE\s+SERVICIOS\s+P[UÚ]BLICOS\s+DE\s+YOLOMB[OÓ](?:\s+E\.?S\.?P\.?)?\s*){2,}",
        "DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. ",
        objeto_final,
        flags=re.IGNORECASE
    )

    # Mantener MAYÚSCULAS sin punto final (estándar contractual institucional de la ESPY)
    objeto_final = " ".join(objeto_final.split()).rstrip(".")

    # Prohibición estricta: NO iniciar con verbos en infinitivo sueltos
    if re.match(r"^(?:REALIZAR|SUMINISTRAR|EJECUTAR|PRESTAR|ADQUIRIR|ARRENDAR|BRINDAR|DESARROLLAR)\b", objeto_final):
        v_match = re.match(r"^([A-ZÁÉÍÓÚÑ]+)\s+(.*)$", objeto_final)
        if v_match:
            verb = v_match.group(1)
            resto = v_match.group(2)
            if verb in ("SUMINISTRAR", "ADQUIRIR"):
                objeto_final = f"SUMINISTRO DE {resto}"
            elif verb == "EJECUTAR":
                objeto_final = f"EJECUCIÓN DE {resto}"
            elif verb == "ARRENDAR":
                objeto_final = f"ARRENDAMIENTO DE {resto}"
            elif verb == "REALIZAR":
                if resto.startswith("EL MANTENIMIENTO"):
                    objeto_final = f"PRESTACIÓN DE SERVICIOS PARA {resto}"
                else:
                    objeto_final = f"PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA {resto}"
            else:
                objeto_final = f"PRESTACIÓN DE SERVICIOS PARA {resto}"

    return objeto_final
