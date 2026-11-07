"""Configuración del Lector Ilustrado.

Las claves de acceso se leen de variables de entorno o del archivo `.env`
ubicado en la carpeta `lector_ilustrado/`. Ese archivo solo existe en el
computador del usuario y está excluido de git.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_ENV = RAIZ / ".env"

CLAVES_EDITABLES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")

VOCES_OPENAI = (
    "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer",
    "verse", "marin", "cedar", "fable", "onyx", "nova",
)


def _leer_env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


@dataclass
class Ajustes:
    anthropic_api_key: str
    openai_api_key: str
    modelo_texto: str
    modelo_imagen: str
    calidad_imagen: str
    modelo_voz: str
    carpeta_datos: Path

    @property
    def tiene_claude(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def tiene_openai(self) -> bool:
        return bool(self.openai_api_key)


def cargar_ajustes() -> Ajustes:
    archivo = _leer_env(ARCHIVO_ENV)

    def valor(nombre: str, defecto: str = "") -> str:
        return os.environ.get(nombre) or archivo.get(nombre) or defecto

    carpeta = Path(valor("LECTOR_DATOS", str(RAIZ / "datos")))
    carpeta.mkdir(parents=True, exist_ok=True)
    return Ajustes(
        anthropic_api_key=valor("ANTHROPIC_API_KEY"),
        openai_api_key=valor("OPENAI_API_KEY"),
        modelo_texto=valor("LECTOR_MODELO_TEXTO", "claude-opus-5-5"),
        modelo_imagen=valor("LECTOR_MODELO_IMAGEN", "gpt-image-2"),
        calidad_imagen=valor("LECTOR_CALIDAD_IMAGEN", "medium"),
        modelo_voz=valor("LECTOR_MODELO_VOZ", "gpt-4o-mini-tts"),
        carpeta_datos=carpeta,
    )


def guardar_claves(nuevas: dict[str, str]) -> None:
    """Guarda (o borra, si el valor llega vacío) claves en el `.env` local."""
    actuales = _leer_env(ARCHIVO_ENV)
    for clave, valor in nuevas.items():
        if clave not in CLAVES_EDITABLES:
            continue
        valor = (valor or "").strip()
        if valor:
            actuales[clave] = valor
        else:
            actuales.pop(clave, None)
    lineas = ["# Claves locales del Lector Ilustrado. No compartir ni subir a git."]
    lineas += [f"{k}={v}" for k, v in actuales.items()]
    ARCHIVO_ENV.write_text("\n".join(lineas) + "\n", encoding="utf-8")
