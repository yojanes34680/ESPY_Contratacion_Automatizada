"""Análisis literario: ficha visual de la obra, escenas y atribución de voces.

Hay dos analistas con la misma interfaz:
- `AnalistaClaude`: usa la API de Anthropic (requiere ANTHROPIC_API_KEY).
- `AnalistaBasico`: reglas simples sin IA, para probar el lector sin costo.
"""
from __future__ import annotations

import json
import re
from typing import Protocol

from pydantic import BaseModel

from .config import VOCES_OPENAI


class Personaje(BaseModel):
    id: str
    nombre: str
    genero: str
    edad_aproximada: str
    descripcion_fisica: str
    vestuario: str
    personalidad_voz: str
    voz: str


class FichaObra(BaseModel):
    titulo: str
    autor: str
    epoca: str
    lugar: str
    contexto_historico: str
    estilo_visual: str
    paleta_colores: str
    tono_narrador: str
    voz_narrador: str
    personajes: list[Personaje]


class Segmento(BaseModel):
    hablante: str
    texto: str
    emocion: str


class Escena(BaseModel):
    titulo: str
    descripcion_imagen: str
    personajes_presentes: list[str]
    segmentos: list[Segmento]


class AnalisisTramo(BaseModel):
    personajes_nuevos: list[Personaje]
    escenas: list[Escena]


class Analista(Protocol):
    def ficha(self, texto_completo: str) -> FichaObra: ...

    def tramo(self, ficha: FichaObra, parrafos: list[str]) -> AnalisisTramo: ...


# --------------------------------------------------------------------------
# Analista con Claude
# --------------------------------------------------------------------------

_LISTA_VOCES = ", ".join(VOCES_OPENAI)

SISTEMA_FICHA = f"""Eres director de arte y director de casting de audiolibros dramatizados.
Lees una obra literaria y preparas su ficha de producción, que después se usa para
ilustrar cada escena y para asignar voces sintéticas a narrador y personajes.

Criterios:
- Deduce época, lugar y contexto histórico a partir de pistas del texto (objetos,
  oficios, transporte, forma de hablar). Si el texto no lo dice, infiere lo más
  plausible y sé concreto (ej.: "Antioquia rural, hacia 1920").
- Propón un estilo visual coherente con el tono de la obra (por ejemplo
  acuarela, óleo costumbrista, grabado, ilustración cinematográfica realista).
- Cada personaje necesita una descripción física estable y detallada (edad,
  complexión, rostro, cabello, rasgos distintivos) y un vestuario propio de la
  época, para que se vea igual en todas las imágenes.
- El `id` de cada personaje es corto, en minúsculas y sin espacios (ej.: "aurelio").
- Asigna a cada personaje y al narrador una voz de esta lista: {_LISTA_VOCES}.
  Varía las voces para que los personajes se distingan entre sí y del narrador.
- `personalidad_voz` y `tono_narrador` son indicaciones de actuación en español
  (edad aparente, acento, ritmo, emoción habitual).
- Incluye solo personajes que hablan o tienen peso visual en la historia."""

SISTEMA_TRAMO = f"""Eres guionista de un audiolibro ilustrado. Recibes la ficha de producción
de la obra y un tramo de texto. Debes dividir el tramo en escenas visuales y
repartir el texto entre el narrador y los personajes.

Reglas para las escenas:
- Una escena agrupa párrafos consecutivos donde la imagen no cambia de forma
  importante (mismo lugar y momento). Evita escenas de menos de 2 párrafos salvo
  que haya un cambio visual fuerte.
- `descripcion_imagen` describe en español, de forma concreta y visual, lo que
  se vería en una ilustración: encuadre, lugar, hora del día, luz, acción,
  expresión de los personajes presentes. Respeta la época y el lugar de la ficha.
  No incluyas texto escrito dentro de la imagen.
- `personajes_presentes` usa los `id` de la ficha.

Reglas para los segmentos (lo más importante):
- Reproduce el texto del tramo COMPLETO, en orden y palabra por palabra, sin
  resumir, corregir ni omitir nada. Solo lo divides.
- `hablante` es "narrador" o el `id` del personaje que pronuncia esas palabras.
- Los diálogos pueden venir marcados con raya (—), semirraya (–) o guion
  corto (-). Los pensamientos entre comillas («») los dice el personaje que
  piensa, con emoción de voz interior.
- En los diálogos, las palabras del personaje van con su `id` y los
  incisos del narrador ("—dijo Juan—", "preguntó sin mirarla") van como
  "narrador". Quita las rayas de diálogo del inicio y del final de cada
  segmento hablado, pero conserva la puntuación interna.
- `emocion` es una indicación breve de actuación (ej.: "cansado y seco",
  "asustada, en voz baja", "sereno").
- Si aparece un personaje que habla y no está en la ficha, agrégalo en
  `personajes_nuevos` con todos sus datos (voz elegida de: {_LISTA_VOCES})."""


class AnalistaClaude:
    def __init__(self, api_key: str, modelo: str = "claude-opus-5-5", esfuerzo: str = "medium"):
        import anthropic

        self._anthropic = anthropic
        self.cliente = anthropic.Anthropic(api_key=api_key)
        self.modelo = modelo
        self.esfuerzo = esfuerzo

    def _pedir(self, sistema: str, contenido: str, formato: type[BaseModel]):
        try:
            return self._pedir_sin_traducir(sistema, contenido, formato)
        except self._anthropic.AuthenticationError:
            raise RuntimeError("La clave de Anthropic no es válida. Revísela en Configuración.")
        except self._anthropic.RateLimitError:
            raise RuntimeError("Anthropic indicó límite de uso o saldo insuficiente. Intente más tarde.")

    def _pedir_sin_traducir(self, sistema: str, contenido: str, formato: type[BaseModel]):
        with self.cliente.beta.messages.stream(
            model=self.modelo,
            max_tokens=64000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": self.esfuerzo},
            output_format=formato,
            system=[{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": contenido}],
        ) as stream:
            mensaje = stream.get_final_message()

        if mensaje.stop_reason == "refusal":
            raise RuntimeError("El modelo se negó a procesar este fragmento del texto.")
        if mensaje.stop_reason == "max_tokens":
            raise RuntimeError("La respuesta quedó incompleta (tramo demasiado largo).")
        resultado = getattr(mensaje, "parsed_output", None)
        if resultado is None:
            texto = next(b.text for b in mensaje.content if b.type == "text")
            resultado = formato.model_validate_json(texto)
        return resultado

    def ficha(self, texto_completo: str) -> FichaObra:
        return self._pedir(
            SISTEMA_FICHA,
            f"<obra>\n{texto_completo}\n</obra>\n\nPrepara la ficha de producción de esta obra.",
            FichaObra,
        )

    def tramo(self, ficha: FichaObra, parrafos: list[str]) -> AnalisisTramo:
        texto = "\n\n".join(parrafos)
        contenido = (
            f"<ficha>\n{ficha.model_dump_json(indent=1)}\n</ficha>\n\n"
            f"<tramo>\n{texto}\n</tramo>\n\n"
            "Divide este tramo en escenas y segmentos según las reglas."
        )
        return self._pedir(SISTEMA_TRAMO, contenido, AnalisisTramo)


# --------------------------------------------------------------------------
# Analista básico (sin IA)
# --------------------------------------------------------------------------

_RAYA = re.compile(r"^\s*[—–-]")
# Separador de diálogo: raya (—), semirraya (–) o guion corto que no une dos palabras.
_SEPARADOR = re.compile(r"\s*(?:[—–]|(?<!\w)-|-(?!\w))\s*")


def _dividir_dialogo(parrafo: str) -> list[Segmento]:
    """Separa un párrafo con rayas de diálogo en voz de personaje y de narrador."""
    if not _RAYA.match(parrafo):
        return [Segmento(hablante="narrador", texto=parrafo, emocion="sereno")]
    crudas = [p.strip() for p in _SEPARADOR.split(parrafo) if p.strip()]
    partes: list[str] = []
    for parte in crudas:
        # "—dijo él—. Luego..." : la puntuación que sigue a la raya cierra el inciso
        signo = re.match(r"^[.,;:]+", parte)
        if signo and partes:
            partes[-1] += signo.group()
            parte = parte[signo.end():].strip()
        if parte:
            partes.append(parte)
    segmentos = []
    for i, parte in enumerate(partes):
        hablante = "personaje" if i % 2 == 0 else "narrador"
        segmentos.append(Segmento(hablante=hablante, texto=parte, emocion="natural"))
    return segmentos


class AnalistaBasico:
    """Sin IA: una escena cada pocos párrafos y diálogos detectados por rayas."""

    def __init__(self, parrafos_por_escena: int = 4):
        self.parrafos_por_escena = parrafos_por_escena

    def ficha(self, texto_completo: str) -> FichaObra:
        hay_dialogo = bool(re.search(r"(^|\n)\s*[—–-]", texto_completo))
        personajes = []
        if hay_dialogo:
            personajes.append(Personaje(
                id="personaje", nombre="Personaje", genero="", edad_aproximada="",
                descripcion_fisica="", vestuario="", personalidad_voz="natural", voz="ash",
            ))
        return FichaObra(
            titulo="", autor="", epoca="", lugar="", contexto_historico="",
            estilo_visual="ilustración", paleta_colores="", tono_narrador="sereno",
            voz_narrador="sage", personajes=personajes,
        )

    def tramo(self, ficha: FichaObra, parrafos: list[str]) -> AnalisisTramo:
        escenas = []
        n = self.parrafos_por_escena
        for i in range(0, len(parrafos), n):
            grupo = parrafos[i:i + n]
            segmentos = [s for p in grupo for s in _dividir_dialogo(p)]
            primera = grupo[0]
            titulo = " ".join(primera.lstrip("—– ").split()[:6]) + "…"
            escenas.append(Escena(
                titulo=titulo,
                descripcion_imagen=" ".join(grupo)[:600],
                personajes_presentes=[],
                segmentos=segmentos,
            ))
        return AnalisisTramo(personajes_nuevos=[], escenas=escenas)


def cobertura(parrafos: list[str], analisis: AnalisisTramo) -> float:
    """Proporción de palabras del original que quedaron en los segmentos."""
    original = len(" ".join(parrafos).split())
    obtenido = sum(len(s.texto.split()) for e in analisis.escenas for s in e.segmentos)
    return obtenido / original if original else 1.0


def json_ficha(ficha: FichaObra) -> str:
    return json.dumps(ficha.model_dump(), ensure_ascii=False, indent=1)
