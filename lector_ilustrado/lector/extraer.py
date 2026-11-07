"""Extracción de texto de PDF/TXT y reconstrucción de párrafos."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

_FIN_ORACION = re.compile(r"[.!?…:»”\"')]\s*$")
_SOLO_NUMERO = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")
_INICIO_PARRAFO = re.compile(r"^\s*([—–\-«“\"]|[A-ZÁÉÍÓÚÑ¿¡])")


def extraer_texto_pdf(ruta: Path, desde: int | None = None, hasta: int | None = None) -> list[str]:
    """Devuelve una lista de páginas (texto crudo). `desde`/`hasta` son 1-indexados."""
    import pdfplumber

    paginas: list[str] = []
    with pdfplumber.open(str(ruta)) as pdf:
        total = len(pdf.pages)
        ini = max(1, desde or 1)
        fin = min(total, hasta or total)
        for numero in range(ini, fin + 1):
            paginas.append(_texto_con_cortes(pdf.pages[numero - 1]))
    return paginas


def _texto_con_cortes(pagina) -> str:
    """Texto de la página con una línea en blanco donde el diseño marca un párrafo.

    Un párrafo nuevo se reconoce por un espacio vertical mayor al normal o por
    una sangría al inicio de la línea.
    """
    lineas = [l for l in pagina.extract_text_lines() if l["text"].strip()]
    if not lineas:
        return ""
    # interlineado normal = el salto vertical más frecuente (el menor si hay empate)
    saltos = Counter(round(b["top"] - a["top"]) for a, b in zip(lineas, lineas[1:]) if b["top"] > a["top"])
    interlineado = min(saltos, key=lambda s: (-saltos[s], s)) if saltos else 0
    margen = min(l["x0"] for l in lineas)
    salida = []
    for i, linea in enumerate(lineas):
        if i:
            salto = linea["top"] - lineas[i - 1]["top"]
            espacio_extra = interlineado and salto > interlineado * 1.45
            sangria = linea["x0"] - margen > 8 and lineas[i - 1]["x0"] - margen <= 8
            if espacio_extra or sangria:
                salida.append("")
        salida.append(linea["text"])
    return "\n".join(salida)


def armar_parrafos(paginas: list[str]) -> list[str]:
    """Une líneas cortadas por el PDF en párrafos completos.

    Reglas: se quitan números de página sueltos, se unen palabras partidas con
    guion al final de línea, y una línea cierra párrafo cuando hay una línea en
    blanco o cuando termina en signo de cierre y es claramente más corta que
    las líneas normales del texto.
    """
    lineas: list[str] = []
    for pagina in paginas:
        for linea in pagina.splitlines():
            if _SOLO_NUMERO.match(linea):
                continue
            lineas.append(linea.rstrip())
        lineas.append("")  # el cambio de página se trata como posible corte

    largas = sorted(len(l) for l in lineas if l.strip())
    ancho_tipico = largas[int(len(largas) * 0.8)] if largas else 80

    parrafos: list[str] = []
    actual = ""
    for i, linea in enumerate(lineas):
        limpia = linea.strip()
        if not limpia:
            # línea en blanco: corta solo si lo anterior parece final de frase
            if actual and _FIN_ORACION.search(actual):
                parrafos.append(actual)
                actual = ""
            continue
        if actual.endswith("-") and not actual.endswith(" -"):
            actual = actual[:-1] + limpia
        elif actual:
            actual = f"{actual} {limpia}"
        else:
            actual = limpia

        siguiente = next((l.strip() for l in lineas[i + 1:] if l.strip()), "")
        corta = len(limpia) < ancho_tipico * 0.75
        if _FIN_ORACION.search(limpia) and corta and (not siguiente or _INICIO_PARRAFO.match(siguiente)):
            parrafos.append(actual)
            actual = ""
    if actual:
        parrafos.append(actual)
    return [re.sub(r"\s+", " ", p).strip() for p in parrafos if p.strip()]


def leer_documento(ruta: Path, desde: int | None = None, hasta: int | None = None) -> list[str]:
    """Lee un PDF o un TXT y devuelve la lista de párrafos."""
    if ruta.suffix.lower() == ".pdf":
        return armar_parrafos(extraer_texto_pdf(ruta, desde, hasta))
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    bloques = re.split(r"\n\s*\n", texto)
    if len(bloques) <= 1:
        bloques = texto.splitlines()
    return [re.sub(r"\s+", " ", b).strip() for b in bloques if b.strip()]


def agrupar_en_tramos(parrafos: list[str], palabras_por_tramo: int = 2500) -> list[list[str]]:
    """Agrupa párrafos en tramos de tamaño manejable para el análisis."""
    tramos: list[list[str]] = []
    actual: list[str] = []
    cuenta = 0
    for p in parrafos:
        n = len(p.split())
        if actual and cuenta + n > palabras_por_tramo:
            tramos.append(actual)
            actual, cuenta = [], 0
        actual.append(p)
        cuenta += n
    if actual:
        tramos.append(actual)
    return tramos
