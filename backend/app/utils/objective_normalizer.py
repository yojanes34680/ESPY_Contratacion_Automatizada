"""Utilidad para normalización y formulación rigurosa de Objetivos Específicos.
Garantiza que todo objetivo específico cumpla la regla metodológica y jurídica:
Iniciar SIEMPRE con un VERBO EN INFINITIVO (ej: Realizar, Ejecutar, Suministrar, Instalar, etc.)
y contar con ortografía técnica impecable, integrando especificaciones y dimensiones subordinadas.
"""
import re
from typing import List, Optional

# Verbos en infinitivo rectores comunes en contratación de servicios públicos (ESP)
INFINITIVE_VERBS = {
    "realizar", "ejecutar", "suministrar", "instalar", "construir",
    "prestar", "implementar", "efectuar", "adecuar", "reponer",
    "demoler", "entregar", "disponer", "capacitar", "verificar",
    "garantizar", "emitir", "practicar", "evaluar", "desarrollar",
    "aplicar", "inspeccionar", "adquirir", "reparar", "manejar",
    "actualizar", "elaborar", "coordinar", "dotar", "adelantar",
    "brindar", "estructurar", "revisar", "hacer", "adelantar"
}

def clean_technical_text(text: str) -> str:
    """Corrige errores comunes de OCR, caracteres pegados, dimensiones y ortografía técnica."""
    s = text.strip()
    if not s:
        return ""

    # Eliminar terminaciones cortadas o fragmentos OCR como ".De", " De", "- "
    s = re.sub(r"^[\-\•\*\s\d\.\,\)]+", "", s).strip()
    s = re.sub(r"[\.\s]+De\s*$", "", s, flags=re.IGNORECASE)

    # Corrección de palabras con primera letra cortada por viñetas OCR
    s = re.sub(r"\b(?:[pP]restaci[oó]n|restaci[oó]n)\b", "Prestación", s)
    s = re.sub(r"\b(?:[dD]iagnosticar|iagnosticar)\b", "Diagnosticar", s)
    s = re.sub(r"\b(?:[eE]jecutar|jecutar)\b", "Ejecutar", s)
    s = re.sub(r"\b(?:[sS]uministrar|uministrar)\b", "Suministrar", s)
    s = re.sub(r"\b(?:[iI]nstalar|nstalar)\b", "Instalar", s)
    s = re.sub(r"\b(?:[rR]ealizar|ealizar)\b", "Realizar", s)
    s = re.sub(r"\b(?:[pP]restar|restar)\b", "Prestar", s)
    s = re.sub(r"\b(?:[gG]arantizar|arantizar)\b", "Garantizar", s)
    s = re.sub(r"\b(?:[vV]erificar|erificar)\b", "Verificar", s)

    # Correcciones ortográficas y de OCR frecuentes en presupuestos y propuestas de obras/servicios
    s = re.sub(r"\bcompectaci[oó]n\b", "compactación", s, flags=re.IGNORECASE)
    s = re.sub(r"\bpriveniente\b", "proveniente", s, flags=re.IGNORECASE)
    s = re.sub(r"\bexcavacign\b", "excavación", s, flags=re.IGNORECASE)
    s = re.sub(r"\bexcavacion\b", "excavación", s, flags=re.IGNORECASE)
    s = re.sub(r"\bseccoion\b", "sección", s, flags=re.IGNORECASE)
    s = re.sub(r"\bseccion\b", "sección", s, flags=re.IGNORECASE)
    s = re.sub(r"\btubieria\b", "tubería", s, flags=re.IGNORECASE)
    s = re.sub(r"\btuberia\b", "tubería", s, flags=re.IGNORECASE)
    s = re.sub(r"\bpresion\b", "presión", s, flags=re.IGNORECASE)
    s = re.sub(r"\breposicion\b", "reposición", s, flags=re.IGNORECASE)
    s = re.sub(r"\binstalacion\b", "instalación", s, flags=re.IGNORECASE)
    s = re.sub(r"\bvalvulas?\b", "válvulas", s, flags=re.IGNORECASE)
    s = re.sub(r"\bvalvulas?compuer[t]?aelasticade", "válvulas de compuerta elástica de ", s, flags=re.IGNORECASE)
    s = re.sub(r"\btransportee\s*", "transporte e ", s, flags=re.IGNORECASE)
    s = re.sub(r"\binstalacionde\s*", "instalación de ", s, flags=re.IGNORECASE)
    s = re.sub(r"\b3\s*RED\s*21\b", "3\" RDE 21", s, flags=re.IGNORECASE)
    s = re.sub(r"\b3RED\s*21\b", "3\" RDE 21", s, flags=re.IGNORECASE)
    s = re.sub(r"(\d+[\"\']?)(?:incluyeaccesoriosy?|incluyendoaccesoriosy?|incluye)", r'\1 incluyendo accesorios y ', s, flags=re.IGNORECASE)
    s = re.sub(r"\bIncluyeaccesoriosy\b", "incluyendo accesorios y ", s, flags=re.IGNORECASE)
    s = re.sub(r"\bincluyeaccesorios\b", "incluyendo accesorios", s, flags=re.IGNORECASE)
    s = re.sub(r"\bincluye\s*accesorios\s*y\b", "incluyendo accesorios y ", s, flags=re.IGNORECASE)

    # Dimensiones OCR como ",60x,80" -> "0.60 x 0.80 m"
    s = re.sub(r",(\d{1,2})\s*[xX]\s*,(\d{1,2})", r"0.\1 x 0.\2 m", s)
    s = re.sub(r"\b0\.(\d{1,2})\s*[xX]\s*0\.(\d{1,2})\b(?!\s*m)", r"0.\1 x 0.\2 m", s)

    # Espacio tras comillas o comas pegadas a letras
    s = re.sub(r'([0-9]+[\"\'])([A-Za-zÁÉÍÓÚáéíóúñÑ])', r'\1 \2', s)
    s = re.sub(r',([A-Za-zÁÉÍÓÚáéíóúñÑ])', r', \1', s)

    # Limpiar conjunciones dobles o finales huérfanas
    s = re.sub(r"\b[yY]\s+[yY]\b", "y", s)
    s = re.sub(r"[\s,]+[yYeE]\s*$", "", s)

    # Colapsar espacios múltiples
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_continuation_line(line: str) -> bool:
    """Detecta si una línea corresponde a una especificación subordinada (dimensiones, coletillas de insumos)."""
    cl = line.strip().lower()
    if not cl:
        return False
    if re.match(r"^(?:secci[oó]n|seccoion)\s+(?:de\s+)?", cl):
        return True
    if re.match(r"^(?:de\s+)?(?:\d+(?:[\.,]\d+)?\s*[xX]\s*\d+|,\d+x,\d+)", cl):
        return True
    if re.match(r"^(?:y\s+)?todo\s+lo\s+necesario\s+para\s+su\s+correcto\s+funcionamiento", cl):
        return True
    if re.match(r"^(?:incluye|incluyendo)\s+accesorios", cl):
        return True
    if cl in ["pun", "und", "m3", "ml", "m2", "global", "gl", "kg"]:
        return True
    return False

def starts_with_infinitive(text: str) -> bool:
    """Determina si la frase comienza gramaticalmente con un verbo en infinitivo."""
    clean = text.strip()
    if not clean:
        return False
    words = clean.split()
    first_word = words[0].lower().rstrip(",:;.")
    if first_word in INFINITIVE_VERBS:
        return True
    # Terminación verbal en infinitivo en español (-ar, -er, -ir) con al menos 4 letras
    if len(first_word) >= 4 and first_word.endswith(("ar", "er", "ir")):
        # Evitar falsos positivos comunes que terminan en ar/er/ir pero son sustantivos
        false_positives = {"lugar", "solar", "militar", "hogar", "primer", "tercer", "mujer", "placer", "chofer", "taller"}
        if first_word not in false_positives:
            return True
    return False

def format_single_objective(text: str) -> str:
    """
    Convierte cualquier actividad, descripción o ítem de propuesta en un objetivo
    específico formal que inicia OBLIGATORIAMENTE con un verbo de acción en infinitivo.
    """
    s = clean_technical_text(text)
    if not s:
        return ""

    def finalize_res(val: str) -> str:
        r = re.sub(r"\s+", " ", val).strip()
        r = re.sub(r"[\s,]+[yYeE]\s*[\.]?$", "", r).strip()
        r = r.rstrip(".")
        # Escribir en minúscula el segundo verbo después de conjunción: 'Suministrar e instalar', 'Habilitar y garantizar'
        r = re.sub(r"\b([eE])\s+([IíÍi])nstalar\b", r"\1 instalar", r)
        r = re.sub(r"\b([yY])\s+([Gg])arantizar\b", r"\1 garantizar", r)
        r = re.sub(r"\b([yY])\s+([Ee])jecutar\b", r"\1 ejecutar", r)
        r = re.sub(r"\b([yY])\s+([Cc])onfigurar\b", r"\1 configurar", r)
        # Preservar siempre en mayúsculas las siglas tecnológicas
        r = re.sub(r"\bgps\b", "GPS", r, flags=re.IGNORECASE)
        r = re.sub(r"\badas/dms\b", "ADAS/DMS", r, flags=re.IGNORECASE)
        r = re.sub(r"\badas\b", "ADAS", r, flags=re.IGNORECASE)
        r = re.sub(r"\bdms\b", "DMS", r, flags=re.IGNORECASE)
        return f"{r}." if r else ""

    # Si ya inicia con verbo en infinitivo, asegurar mayúscula y puntuación
    if starts_with_infinitive(s):
        res = s[0].upper() + s[1:]
        return finalize_res(res)

    # Transformación de sustantivos comunes a infinitivo técnico
    patterns = [
        # Suministro, transporte e instalación
        (r"^Suministro,?\s*transporte\s*e\s*instalaci[oó]n\s+(?:de\s+)?", "Suministrar, transportar e instalar "),
        (r"^Suministro\s+y\s+(?:puesta\s+en\s+marcha|instalaci[oó]n)\s+(?:de\s+)?", "Suministrar e instalar "),
        (r"^Suministro,?\s*transporte\s+y\s+entrega\s+(?:de\s+)?", "Suministrar, transportar y entregar "),
        (r"^Suministro\s+(?:de\s+)?", "Suministrar "),

        # Excavación (como el ejemplo explícito del usuario)
        (r"^Excavaci[oó]n\s+manual\b", "Realizar excavación manual"),
        (r"^Excavaci[oó]n\s+mec[aá]nica\b", "Realizar excavación mecánica"),
        (r"^Excavaci[oó]n\s+(?:de\s+|en\s+)?", "Realizar excavación "),

        # Rotura y demolición de pavimentos / estructuras
        (r"^Rotura\s+(?:de\s+)?pavimento\b", "Realizar rotura de pavimento"),
        (r"^Rotura\s+(?:de\s+)?", "Realizar la rotura de "),
        (r"^Demolici[oó]n\s+(?:de\s+)?", "Realizar la demolición de "),

        # Llenos y compactación
        (r"^Lleno\s+y\s+compactaci[oó]n\b", "Realizar lleno y compactación"),
        (r"^Llenos?\s+manual(?:es)?\b", "Realizar lleno manual"),
        (r"^Llenos?\s+(?:con\s+|y\s+)?", "Realizar el llenado y compactación "),

        # Reposición
        (r"^Reposici[oó]n\s+(?:de\s+)?pavimento\b", "Realizar reposición de pavimento"),
        (r"^Reposici[oó]n\s+(?:de\s+)?", "Realizar la reposición de "),

        # Obras, montajes e ingeniería
        (r"^Instalaci[oó]n\s+(?:de\s+)?", "Instalar "),
        (r"^Construcci[oó]n\s+(?:de\s+)?", "Construir "),
        (r"^Mantenimiento\s+(?:preventivo\s+y\s+correctivo\s+)?(?:de|a)\s+", "Realizar el mantenimiento de "),
        (r"^Mantenimiento\s+(?:de|a)\s+", "Realizar el mantenimiento de "),
        (r"^Adecuaci[oó]n\s+(?:de\s+)?", "Adecuar "),
        (r"^Reparaci[oó]n\s+(?:de\s+)?", "Reparar "),
        (r"^Transporte\s+(?:de\s+)?", "Transportar "),
        (r"^Disposici[oó]n\s+(?:final\s+)?(?:de\s+)?", "Efectuar la disposición final de "),
        (r"^Entrega\s+(?:de\s+)?", "Entregar "),
        (r"^Pr[aá]ctica\s+(?:de\s+)?", "Practicar "),
        (r"^Emisi[oó]n\s+(?:de\s+)?", "Emitir "),
        (r"^Valoraci[oó]n\s+(?:de\s+)?", "Realizar la valoración de "),
        (r"^Elaboraci[oó]n\s+(?:de\s+)?", "Elaborar "),
        (r"^Revisi[oó]n\s+(?:de\s+)?", "Revisar "),
        (r"^Implementaci[oó]n\s+(?:de\s+)?", "Implementar "),
        (r"^Adquisici[oó]n\s+(?:de\s+)?", "Adquirir "),
        (r"^Aplicaci[oó]n\s+(?:de\s+)?", "Aplicar "),
        (r"^Succi[oó]n\s+(?:de\s+)?", "Realizar la succión de "),
        (r"^Retiro\s+(?:de\s+)?", "Realizar el retiro de "),
        (r"^Verificaci[oó]n\s+(?:de\s+)?", "Verificar ")
    ]

    for pat, repl in patterns:
        if re.search(pat, s, re.IGNORECASE):
            s = re.sub(pat, repl, s, count=1, flags=re.IGNORECASE)
            res = s[0].upper() + s[1:]
            return finalize_res(res)

    # Limpieza de prefijos comunes no verbales ("El ", "La ", "Los ", "Las ")
    s_clean = re.sub(r"^(?:el|la|los|las)\s+", "", s, flags=re.IGNORECASE)

    # Si todavía no tiene verbo en infinitivo al inicio, anteponer "Realizar "
    res = f"Realizar {s_clean[0].lower() + s_clean[1:]}"
    res = res[0].upper() + res[1:]
    return finalize_res(res)

def normalize_objetivos_especificos(raw_items: Optional[List[str]]) -> List[str]:
    """
    Recibe una lista de actividades u objetivos y devuelve una lista estandarizada:
    1. Agrupa líneas de especificación secundaria con su ítem principal.
    2. Convierte cada objetivo para que inicie obligatoriamente con un verbo en infinitivo.
    3. Corrige ortografía y problemas de digitalización.
    4. Elimina duplicados y mantiene consistencia técnica.
    """
    if not raw_items:
        return []

    merged_items: List[str] = []
    for item in raw_items:
        if not item or not isinstance(item, str):
            continue
        txt = clean_technical_text(item)
        if not txt:
            continue

        # Si es una línea de continuación (dimensiones, coletillas técnicas)
        if is_continuation_line(txt) and merged_items:
            prev = merged_items[-1].rstrip(" .;")
            prev = re.sub(r"\s+[yY]\s*$", "", prev)
            clean_cont = re.sub(r"^[yY]\s+", "", txt.strip())

            if re.match(r"^(?:secci[oó]n|seccoion|de\s+0\.)", clean_cont, re.IGNORECASE):
                merged_items[-1] = f"{prev}, con {clean_cont.lower()}"
            elif re.match(r"^todo\s+lo\s+necesario", clean_cont, re.IGNORECASE):
                merged_items[-1] = f"{prev} y {clean_cont.lower()}"
            elif re.match(r"^(?:incluye|incluyendo)", clean_cont, re.IGNORECASE):
                merged_items[-1] = f"{prev}, {clean_cont.lower()}"
            else:
                merged_items[-1] = f"{prev} ({clean_cont})"
        else:
            merged_items.append(txt)

    result: List[str] = []
    seen = set()
    for it in merged_items:
        obj = format_single_objective(it)
        if obj and len(obj) >= 8:
            key = obj.lower().rstrip(".")
            if key not in seen:
                seen.add(key)
                result.append(obj)

    return result
