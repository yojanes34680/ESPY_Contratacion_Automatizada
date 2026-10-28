"""Módulo de limpieza, saneamiento y formateo de texto del Certificado de Disponibilidad Presupuestal (CDP).
Asegura que el marcador {{CDP}} inyectado en Estudio Previo, Minuta y Acta de Inicio
contenga únicamente: Número, Fecha, Valor y Rubro Presupuestal, cortando cualquier
bloque residual de clasificadores presupuestales CCPET, pies de página de Sistemas Aries,
valores en letras o texto administrativo.
"""
import re
from typing import Optional, List, Dict, Any

import json
from pathlib import Path
from functools import lru_cache

JSON_RESOURCES_PATH = Path(__file__).resolve().parent.parent / "resources" / "cdp_marcas_corte.json"

FALLBACK_MARCAS_DE_CORTE_CDP = [
    r",?\s*y\s+respaldado\s+en\s+los\s+clasificadores",
    r"clasificadores\s+presupuestales",
    r"\bCCPET\b",
    r"\bCCPET\d+\b",
    r"\bClasificador\s+Valor\b",
    r"\bValor\s+Clasificador\b",
    r"\bValor\s+en\s+letras\b",
    r"\bValoren\s*letras\b",
    r"\bObjeto\s+de\s+la\s+Disponibilidad\b",
    r"\bObjetado\s+la\s+Disponibilidad\b",
    r"\bDesarrollado\s+por\s+Sistemas\s+Aries\b",
    r"\bDesarrollado\s+por\b",
    r"\bImpreso\s+por\b",
    r"\bVersi[oó]n\s+AriesNet\b",
]

@lru_cache(maxsize=1)
def get_marcas_de_corte_cdp() -> List[str]:
    """Carga y cachea la lista oficial de marcas de corte desde el recurso JSON."""
    if JSON_RESOURCES_PATH.exists():
        try:
            with open(JSON_RESOURCES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass
    return list(FALLBACK_MARCAS_DE_CORTE_CDP)

MARCAS_DE_CORTE_CDP = get_marcas_de_corte_cdp()

@lru_cache(maxsize=1)
def get_patron_corte_cdp() -> re.Pattern:
    """Retorna el patrón regex compilado basado en las marcas oficiales."""
    marcas = get_marcas_de_corte_cdp()
    return re.compile("|".join(marcas), flags=re.IGNORECASE)

PATRON_CORTE_CDP = get_patron_corte_cdp()


def limpiar_texto_cdp(texto: Optional[str]) -> str:
    """
    Función de seguridad que sanea el texto del CDP.
    Corta el texto en la primera aparición de cualquiera de las marcas de clasificadores,
    valores en letras o pie de página contable.
    Elimina comas, espacios y guiones sobrantes al final y garantiza que termine en punto.
    Si el texto es nulo o vacío, retorna cadena vacía.
    """
    if not texto:
        return ""
    
    txt = str(texto).strip()
    if not txt:
        return ""

    # Buscar la primera coincidencia de corte
    match = PATRON_CORTE_CDP.search(txt)
    if match:
        txt = txt[:match.start()].strip()

    # Limpiar comas, puntos y espacios sobrantes al final
    txt = re.sub(r"[\s,;:\-]+$", "", txt).strip()
    
    if txt and not txt.endswith("."):
        txt += "."

    return txt


def construir_texto_cdp(
    numero: Optional[str],
    fecha_texto: Optional[str],
    valor_fmt: Optional[str],
    rubros: List[Dict[str, str]]
) -> str:
    """
    Construye el texto limpio de {{CDP}} para uno o varios rubros presupuestales.
    Formato:
    - Un rubro:
      {numero}, expedido el {fecha}, por valor de ${valor}, con cargo al Rubro Presupuestal {codigo} – {nombre}.
    - Varios rubros:
      {numero}, expedido el {fecha}, por valor de ${valor}, con cargo a los Rubros Presupuestales {codigo1} – {nombre1} y {codigo2} – {nombre2}.
    """
    num = str(numero).strip() if numero else "000"
    parts = [num]

    if fecha_texto and str(fecha_texto).strip():
        parts.append(f"expedido el {str(fecha_texto).strip()}")

    if valor_fmt and str(valor_fmt).strip():
        v = str(valor_fmt).strip()
        if not v.startswith("$"):
            v = f"${v}"
        parts.append(f"por valor de {v}")

    # Filtrar rubros válidos
    rubros_validos = []
    for r in (rubros or []):
        cod = str(r.get("codigo") or "").strip()
        nom = str(r.get("nombre") or "").strip()
        # Cortar cualquier residuo en el nombre
        if nom:
            match_nom = PATRON_CORTE_CDP.search(nom)
            if match_nom:
                nom = nom[:match_nom.start()].strip()
            nom = re.sub(r"[\s,;:\-]+$", "", nom).strip()

        if cod and nom:
            rubros_validos.append(f"{cod} – {nom}")
        elif cod:
            rubros_validos.append(cod)
        elif nom:
            rubros_validos.append(nom)

    if len(rubros_validos) == 1:
        parts.append(f"con cargo al Rubro Presupuestal {rubros_validos[0]}")
    elif len(rubros_validos) > 1:
        primeros = ", ".join(rubros_validos[:-1])
        rubros_str = f"{primeros} y {rubros_validos[-1]}"
        parts.append(f"con cargo a los Rubros Presupuestales {rubros_str}")

    return limpiar_texto_cdp(", ".join(parts))
