"""Generación de imágenes y de voces."""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

from .analizar import Escena, FichaObra, Personaje

# --------------------------------------------------------------------------
# Imágenes
# --------------------------------------------------------------------------


def prompt_imagen(ficha: FichaObra, escena: Escena, personajes: dict[str, Personaje]) -> str:
    """Arma la instrucción de imagen combinando la ficha de la obra y la escena."""
    partes = [
        f"Ilustración para un libro, estilo: {ficha.estilo_visual}.",
    ]
    if ficha.paleta_colores:
        partes.append(f"Paleta de color: {ficha.paleta_colores}.")
    if ficha.epoca or ficha.lugar:
        partes.append(f"Ambientación: {ficha.lugar}, {ficha.epoca}. {ficha.contexto_historico}".strip())
    partes.append(f"Escena: {escena.descripcion_imagen}")
    for pid in escena.personajes_presentes:
        p = personajes.get(pid)
        if p and p.descripcion_fisica:
            partes.append(f"{p.nombre}: {p.descripcion_fisica}. Viste: {p.vestuario}.")
    partes.append(
        "Respeta con rigor la época: sin objetos, ropa ni tecnología anacrónicos. "
        "Sin textos, letras, subtítulos ni marcas de agua dentro de la imagen."
    )
    return "\n".join(partes)


class IlustradorOpenAI:
    extension = "png"

    def __init__(self, api_key: str, modelo: str, calidad: str = "medium"):
        import openai

        self.cliente = openai.OpenAI(api_key=api_key)
        self.modelo = modelo
        self.calidad = calidad

    def generar(self, prompt: str, destino: Path) -> Path:
        respuesta = self.cliente.images.generate(
            model=self.modelo,
            prompt=prompt,
            size="1536x1024",
            quality=self.calidad,
            n=1,
        )
        datos = respuesta.data[0].b64_json
        destino = destino.with_suffix(".png")
        destino.write_bytes(base64.b64decode(datos))
        return destino


class IlustradorProvisional:
    """Genera una lámina SVG con el título de la escena (sin costo)."""

    extension = "svg"
    _COLORES = [("#3b2a1a", "#a8743a"), ("#1d2b36", "#4f7a8a"), ("#2c2236", "#8a5a7a"),
                ("#233024", "#6f8a4f"), ("#3a1f1f", "#9a5040")]

    def __init__(self):
        self._n = 0

    def generar(self, prompt: str, destino: Path, titulo: str = "") -> Path:
        c1, c2 = self._COLORES[self._n % len(self._COLORES)]
        self._n += 1
        texto = html.escape(titulo or "Escena")
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1536 1024">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="1536" height="1024" fill="url(#g)"/>
<text x="768" y="500" font-family="Georgia, serif" font-size="54" fill="#f4ead8" text-anchor="middle">{texto}</text>
<text x="768" y="580" font-family="Georgia, serif" font-size="28" fill="#f4ead8" opacity=".7" text-anchor="middle">imagen provisional · configure la clave de imágenes</text>
</svg>"""
        destino = destino.with_suffix(".svg")
        destino.write_text(svg, encoding="utf-8")
        return destino


# --------------------------------------------------------------------------
# Voces
# --------------------------------------------------------------------------

LIMITE_TTS = 3500


def trocear_para_voz(texto: str, limite: int = LIMITE_TTS) -> list[str]:
    """Divide textos largos por oraciones para respetar el límite del servicio de voz."""
    if len(texto) <= limite:
        return [texto]
    oraciones = re.split(r"(?<=[.!?…])\s+", texto)
    trozos, actual = [], ""
    for o in oraciones:
        if actual and len(actual) + len(o) + 1 > limite:
            trozos.append(actual)
            actual = o
        else:
            actual = f"{actual} {o}".strip()
    if actual:
        trozos.append(actual)
    return trozos


class NarradorOpenAI:
    def __init__(self, api_key: str, modelo: str):
        import openai

        self.cliente = openai.OpenAI(api_key=api_key)
        self.modelo = modelo

    def generar(self, texto: str, voz: str, indicaciones: str, destino: Path) -> Path:
        destino = destino.with_suffix(".mp3")
        audio = b""
        for trozo in trocear_para_voz(texto):
            respuesta = self.cliente.audio.speech.create(
                model=self.modelo,
                voice=voz,
                input=trozo,
                instructions=indicaciones,
                response_format="mp3",
            )
            audio += respuesta.content
        destino.write_bytes(audio)
        return destino


def indicaciones_voz(ficha: FichaObra, hablante: str, emocion: str,
                     personajes: dict[str, Personaje]) -> tuple[str, str]:
    """Devuelve (voz, indicaciones de actuación) para un segmento."""
    base = "Habla en español latinoamericano neutro, con dicción clara."
    if hablante == "narrador" or hablante not in personajes:
        voz = ficha.voz_narrador or "sage"
        texto = f"{base} Eres el narrador de un audiolibro. Tono: {ficha.tono_narrador}. Matiz: {emocion}."
    else:
        p = personajes[hablante]
        voz = p.voz or "ash"
        texto = (f"{base} Interpretas a {p.nombre} ({p.genero}, {p.edad_aproximada}). "
                 f"Voz y carácter: {p.personalidad_voz}. Emoción en esta línea: {emocion}.")
    return voz, texto
