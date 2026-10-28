"""Reglas y utilidades de nomenclatura oficial para contratos de la ESP Yolombó.

Norma Institucional Obligatoria:
- Prestación de Servicios -> Sigla obligatoria: CPS (Ej: CPS-050-2026)
- Suministro             -> Sigla obligatoria: CS  (Ej: CS-054-2026)
- Arrendamiento          -> Sigla obligatoria: CA  (Ej: CA-013-2026)
- Obra                   -> Sigla obligatoria: CO  (Ej: CO-029-2026)
- Consultoría            -> Sigla obligatoria: CC  (Ej: CC-001-2026)
- Interventoría          -> Sigla obligatoria: CI  (Ej: CI-001-2026)
"""
import re
from typing import Any, Tuple, Optional
from datetime import datetime

PREFIX_BY_TIPOLOGIA = {
    "PRESTACION_SERVICIOS": "CPS",
    "SUMINISTRO": "CS",
    "ARRENDAMIENTO": "CA",
    "OBRA": "CO",
    "CONSULTORIA": "CC",
    "INTERVENTORIA": "CI",
}

KNOWN_PREFIXES = {"CPS", "CS", "CA", "CO", "CC", "CI"}


def infer_contract_tipologia(
    propuesta_text: str,
    cdp_text: str = "",
    current_tipologia: Optional[str] = None
) -> Tuple[str, bool]:
    """
    Infiere de manera inteligente la tipología contractual y si comprende servicio conexo,
    analizando el texto de la propuesta económica y/o del CDP.

    Reglas en orden de prelación:
    a) Obra Civil ('OBRA'): Si contiene tabla con A.I.U. (Administración, Imprevistos, Utilidad)
       o partidas de obra civil (localización y replanteo, excavación, concreto, demolición,
       muro de contención, cuneta, etc.) -> ('OBRA', False).
    b) Arrendamiento ('ARRENDAMIENTO'): Si trata de canon/alquiler de bien inmueble o vehículo
       sin transferencia de dominio -> ('ARRENDAMIENTO', False).
    c) Suministro ('SUMINISTRO'):
       - Si la propuesta indica expresamente 'Modalidad: COMPRA' o 'COMPRAVENTA', o cotiza
         bienes físicos/equipos/insumos (unidades GPS, cámaras, micro sd, memorias, tuberías,
         químicos, papelería, dotación, herramientas, hardware) de forma preponderante; O
       - Si el CDP asociado tiene rubros presupuestales de adquisición de bienes/activos/maquinaria
         ('MAQUINARIA', 'EQUIPOS', 'MATERIALES Y SUMINISTROS', '2.1.2.01', '2.3.2.01', '2.1.2.02.01', '2.3.2.02.01')
       -> Retorna ('SUMINISTRO', has_installation_or_monitoring_service).
    d) En los demás casos (asesoría profesional, apoyo a la gestión, sensibilización PGIRS sin compra preponderante,
       mantenimiento puro sin venta de equipos nuevos) -> ('PRESTACION_SERVICIOS', False).
    """
    text_prop = (propuesta_text or "").lower()
    text_cdp = (cdp_text or "").lower()
    full_text = f"{text_prop} {text_cdp}".strip()

    if not full_text:
        curr = (current_tipologia or "PRESTACION_SERVICIOS").upper().strip()
        is_sum = "SUMINISTRO" in curr or "COMPRA" in curr
        return (curr if curr in PREFIX_BY_TIPOLOGIA else "PRESTACION_SERVICIOS", False)

    # a) Regla de Obra Civil
    has_aiu = bool(re.search(r"\ba\.?i\.?u\.?\b|\badministraci[oó]n,\s*imprevistos\s*y\s*utilidad\b", full_text))
    has_obra_partidas = bool(re.search(
        r"\b(?:localizaci[oó]n\s+y\s+replanteo|excavaci[oó]n\s+(?:manual|mec[aá]nica)|rotura\s+de\s+pavimento|demolici[oó]n\s+de|llenos?\s+compactad[oa]s?|muro\s+de\s+contenci[oó]n|cunetas?|obras?\s+civiles?)\b",
        full_text
    ))
    # Excluir si solo es mantenimiento de herramientas o suministro de materiales
    if (has_aiu or has_obra_partidas) and not re.search(r"\bmantenimiento\s+(?:de\s+)?herramientas\b", text_prop):
        # Si tiene A.I.U. o múltiples actividades de obra civil
        if has_aiu or re.search(r"\b(?:concreto|pavimento|excavaci[oó]n)\b", full_text):
            return ("OBRA", False)

    # b) Regla de Arrendamiento
    has_arriendo = bool(re.search(
        r"\b(?:arrendamiento\s+de|canon\s+de\s+arrendamiento|alquiler\s+de\s+veh[ií]culo|arriendo\s+de\s+veh[ií]culo|arrendamiento\s+de\s+inmueble)\b",
        full_text
    )) and not bool(re.search(r"\b(?:compra|venta|suministro)\b", text_prop))
    if has_arriendo:
        return ("ARRENDAMIENTO", False)

    # c) Regla de Suministro (Factor Preponderante y Modalidad Compra)
    has_modalidad_compra = bool(re.search(
        r"\b(?:modalidad\s*:\s*compra|inversi[oó]n\s+inicial\s+compra|compraventa|adquisici[oó]n\s+de\s+equipos?)\b",
        text_prop
    ))
    
    # CDP con rubros de maquinaria, equipos, materiales o suministros
    has_cdp_bienes = bool(re.search(
        r"\b(?:2\.1\.2\.01|2\.3\.2\.01|2\.1\.2\.02\.01|2\.3\.2\.02\.01|maquinaria\s+de\s+inform[aá]tica|maquinaria\s+y\s+equipo|materiales\s+y\s+suministros|adquisici[oó]n\s+de\s+bienes)\b",
        text_cdp
    ))

    # Palabras clave de bienes físicos preponderantes en cotización
    has_hardware_or_goods = bool(re.search(
        r"\b(?:unidad\s+gps|unidades\s+gps|c[aá]mara(?:s)?|ci05f|jc371|microsd|memoria(?:s)?\s+micro\s*sd|tuber[ií]as?|qu[ií]micos?|dotaci[oó]n|overoles?|botas?|canecas?|contenedores?|bolsas?|papeler[ií]a|computador(?:es)?|impresora(?:s)?)\b",
        text_prop
    ))

    # Verificar si el valor de compra de equipos supera el 50% del total
    # Si la propuesta tiene "RESUMEN INVERSION INICIAL COMPRA" y "RESUMEN INVERSION RECURRENTE"
    has_installation_or_service = bool(re.search(
        r"\b(?:instalaci[oó]n|monitoreo|plataforma|mantenimiento|servicio\s+conexo)\b",
        text_prop
    ))

    if has_modalidad_compra or has_cdp_bienes:
        return ("SUMINISTRO", has_installation_or_service)

    if has_hardware_or_goods and not re.search(r"\bmantenimiento\s+a\s+todo\s+costo\s+de\s+herramientas\b", text_prop):
        # Si es compra/suministro explícito de bienes o insumos (ej. Asocomunal bolsas/canecas/plantas)
        if any(w in text_prop for w in ["compra", "suministro", "adquisicion", "adquisición", "dotacion", "dotación", "entrega"]):
            return ("SUMINISTRO", has_installation_or_service)
        if bool(re.search(r"\b(?:unidad\s+gps|microsd|ci05f|jc371)\b", text_prop)):
            return ("SUMINISTRO", has_installation_or_service)

    # d) Si el usuario ya especificó SUMINISTRO
    if current_tipologia and "SUMINISTRO" in current_tipologia.upper():
        return ("SUMINISTRO", has_installation_or_service)

    if current_tipologia and "OBRA" in current_tipologia.upper():
        return ("OBRA", False)

    if current_tipologia and "ARRENDAMIENTO" in current_tipologia.upper():
        return ("ARRENDAMIENTO", False)

    # Fallback: Prestación de Servicios
    return ("PRESTACION_SERVICIOS", False)



def get_required_prefix(tipologia: Any) -> str:
    """Devuelve la sigla oficial correspondiente a la tipología contractual."""
    tipo_str = str(getattr(tipologia, "value", tipologia) or "").upper().strip()
    
    if "SUMINISTRO" in tipo_str:
        return "CS"
    elif "ARRENDAMIENTO" in tipo_str:
        return "CA"
    elif "OBRA" in tipo_str:
        return "CO"
    elif "CONSULTORIA" in tipo_str:
        return "CC"
    elif "INTERVENTORIA" in tipo_str:
        return "CI"
    # Fallback y servicios por defecto
    return "CPS"


def normalize_contract_code(numero: str, tipologia: Any, vigencia: Optional[int] = None) -> str:
    """
    Normaliza el código/número de contrato garantizando que use la sigla obligatoria según su tipología.
    Ejemplos:
    - 'CPS-054-2026' con SUMINISTRO -> 'CS-054-2026'
    - 'CS-050-2026' con PRESTACION_SERVICIOS -> 'CPS-050-2026'
    - '054' con SUMINISTRO y vigencia 2026 -> 'CS-054-2026'
    - '054-2026' con OBRA -> 'CO-054-2026'
    """
    if not numero or not str(numero).strip():
        return numero

    clean = str(numero).strip().upper()
    req_prefix = get_required_prefix(tipologia)
    v_year = vigencia or datetime.now().year

    # Patrón 1: SIGLA-CONSECUTIVO-AÑO (ej: CPS-054-2026, CS-012-2026)
    m_full = re.match(r"^([A-Z]{2,4})-(\d+)-(\d{4})$", clean)
    if m_full:
        cur_pfx, consecutivo, year = m_full.group(1), m_full.group(2), m_full.group(3)
        return f"{req_prefix}-{consecutivo}-{year}"

    # Patrón 2: SIGLA-CONSECUTIVO (ej: CPS-054)
    m_pfx_num = re.match(r"^([A-Z]{2,4})-(\d+)$", clean)
    if m_pfx_num:
        cur_pfx, consecutivo = m_pfx_num.group(1), m_pfx_num.group(2)
        return f"{req_prefix}-{consecutivo}-{v_year}"

    # Patrón 3: Solo dígitos (ej: "054" o "54")
    m_digits = re.match(r"^(\d+)$", clean)
    if m_digits:
        val = int(m_digits.group(1))
        return f"{req_prefix}-{val:03d}-{v_year}"

    # Patrón 4: Digitos-Año (ej: "054-2026")
    m_digits_year = re.match(r"^(\d+)-(\d{4})$", clean)
    if m_digits_year:
        val = int(m_digits_year.group(1))
        year = m_digits_year.group(2)
        return f"{req_prefix}-{val:03d}-{year}"

    # Patrón 5: Genérico con guión pero sigla desconocida o no canónica
    m_generic = re.match(r"^([A-Z0-9]+)-(.*)$", clean)
    if m_generic:
        pfx_cand, rest = m_generic.group(1), m_generic.group(2)
        if pfx_cand in KNOWN_PREFIXES:
            return f"{req_prefix}-{rest}"

    return clean
