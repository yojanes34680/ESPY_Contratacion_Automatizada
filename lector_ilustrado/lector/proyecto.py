"""Proyectos: cada obra cargada vive en `datos/<id>/` con su `proyecto.json`."""
from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
import uuid
from pathlib import Path

from .analizar import (AnalisisTramo, AnalistaBasico, AnalistaClaude, FichaObra,
                       Personaje, cobertura)
from .config import Ajustes
from .extraer import agrupar_en_tramos, leer_documento
from .medios import (IlustradorOpenAI, IlustradorProvisional, NarradorOpenAI,
                     indicaciones_voz, prompt_imagen)

_candado = threading.Lock()

OPCIONES_DEFECTO = {
    "desde": None,           # página inicial (PDF)
    "hasta": None,           # página final (PDF)
    "max_escenas": 12,       # tope para controlar costos
    "analisis": "claude",    # "claude" | "basico"
    "imagenes": "openai",    # "openai" | "provisional"
    "voces": "openai",       # "openai" | "navegador"
}


def carpeta(ajustes: Ajustes, pid: str) -> Path:
    if not pid.replace("-", "").isalnum():
        raise ValueError("Identificador inválido")
    return ajustes.carpeta_datos / pid


def leer(ajustes: Ajustes, pid: str) -> dict:
    ruta = carpeta(ajustes, pid) / "proyecto.json"
    with _candado:
        return json.loads(ruta.read_text(encoding="utf-8"))


def guardar(ajustes: Ajustes, datos: dict) -> None:
    ruta = carpeta(ajustes, datos["id"]) / "proyecto.json"
    tmp = ruta.with_suffix(".tmp")
    with _candado:
        tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(ruta)


def listar(ajustes: Ajustes) -> list[dict]:
    proyectos = []
    for ruta in sorted(ajustes.carpeta_datos.glob("*/proyecto.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        portada = next((e["imagen"] for e in d.get("escenas", []) if e.get("imagen")), None)
        proyectos.append({
            "id": d["id"], "titulo": (d.get("ficha") or {}).get("titulo") or d["nombre_archivo"],
            "autor": (d.get("ficha") or {}).get("autor", ""), "estado": d["estado"],
            "escenas": len(d.get("escenas", [])), "portada": portada, "creado": d["creado"],
        })
    return proyectos


def crear(ajustes: Ajustes, nombre_archivo: str, contenido: bytes, opciones: dict) -> dict:
    pid = uuid.uuid4().hex[:12]
    base = carpeta(ajustes, pid)
    (base / "img").mkdir(parents=True)
    (base / "audio").mkdir()
    extension = Path(nombre_archivo).suffix.lower() or ".pdf"
    (base / f"original{extension}").write_bytes(contenido)
    datos = {
        "id": pid,
        "nombre_archivo": nombre_archivo,
        "archivo": f"original{extension}",
        "creado": time.strftime("%Y-%m-%d %H:%M"),
        "estado": "en_cola",
        "progreso": {"paso": "En cola", "hecho": 0, "total": 0},
        "opciones": {**OPCIONES_DEFECTO, **{k: v for k, v in opciones.items() if k in OPCIONES_DEFECTO}},
        "ficha": None,
        "escenas": [],
        "advertencias": [],
        "error": None,
    }
    guardar(ajustes, datos)
    return datos


def eliminar(ajustes: Ajustes, pid: str) -> None:
    shutil.rmtree(carpeta(ajustes, pid), ignore_errors=True)


# --------------------------------------------------------------------------
# Procesamiento
# --------------------------------------------------------------------------


def _analista(ajustes: Ajustes, opciones: dict):
    if opciones["analisis"] == "claude":
        if not ajustes.tiene_claude:
            raise RuntimeError("Falta la clave de Anthropic (Claude). Agréguela en Configuración.")
        return AnalistaClaude(ajustes.anthropic_api_key, ajustes.modelo_texto)
    return AnalistaBasico()


def _ilustrador(ajustes: Ajustes, opciones: dict):
    if opciones["imagenes"] == "openai":
        if not ajustes.tiene_openai:
            raise RuntimeError("Falta la clave de OpenAI para imágenes. Agréguela en Configuración.")
        return IlustradorOpenAI(ajustes.openai_api_key, ajustes.modelo_imagen, ajustes.calidad_imagen)
    return IlustradorProvisional()


def _narrador(ajustes: Ajustes, opciones: dict):
    if opciones["voces"] == "openai":
        if not ajustes.tiene_openai:
            raise RuntimeError("Falta la clave de OpenAI para voces. Agréguela en Configuración.")
        return NarradorOpenAI(ajustes.openai_api_key, ajustes.modelo_voz)
    return None  # el navegador lee en voz alta


def _personajes(datos: dict) -> dict[str, Personaje]:
    return {p["id"]: Personaje(**p) for p in (datos["ficha"] or {}).get("personajes", [])}


def _paso(ajustes: Ajustes, datos: dict, estado: str, paso: str, hecho: int = 0, total: int = 0):
    datos["estado"] = estado
    datos["progreso"] = {"paso": paso, "hecho": hecho, "total": total}
    guardar(ajustes, datos)


def procesar(ajustes: Ajustes, pid: str, analista=None, ilustrador=None, narrador=None) -> dict:
    """Ejecuta todo el flujo. Guarda avances para que el lector muestre lo ya listo."""
    datos = leer(ajustes, pid)
    base = carpeta(ajustes, pid)
    op = datos["opciones"]
    try:
        analista = analista or _analista(ajustes, op)
        ilustrador = ilustrador or _ilustrador(ajustes, op)
        narrador = narrador if narrador is not None else _narrador(ajustes, op)

        _paso(ajustes, datos, "extrayendo", "Leyendo el documento")
        parrafos = leer_documento(base / datos["archivo"], op.get("desde"), op.get("hasta"))
        if not parrafos:
            raise RuntimeError("No se encontró texto. ¿Es un PDF escaneado (solo imágenes)?")

        _paso(ajustes, datos, "analizando", "Estudiando época, lugar y personajes")
        ficha = analista.ficha("\n\n".join(parrafos))
        if not ficha.titulo.strip():
            ficha.titulo = Path(datos["nombre_archivo"]).stem.replace("_", " ")
        datos["ficha"] = ficha.model_dump()
        guardar(ajustes, datos)

        tramos = agrupar_en_tramos(parrafos)
        max_escenas = int(op.get("max_escenas") or 0)
        for i, tramo in enumerate(tramos, 1):
            if max_escenas and len(datos["escenas"]) >= max_escenas:
                break
            _paso(ajustes, datos, "analizando", "Dividiendo en escenas y voces", i, len(tramos))
            analisis: AnalisisTramo = analista.tramo(FichaObra(**datos["ficha"]), tramo)
            proporcion = cobertura(tramo, analisis)
            if proporcion < 0.9:
                datos["advertencias"].append(
                    f"En el tramo {i} el análisis conservó solo el {proporcion:.0%} del texto.")
            conocidos = {p["id"] for p in datos["ficha"]["personajes"]}
            for nuevo in analisis.personajes_nuevos:
                if nuevo.id not in conocidos:
                    datos["ficha"]["personajes"].append(nuevo.model_dump())
                    conocidos.add(nuevo.id)
            for escena in analisis.escenas:
                if max_escenas and len(datos["escenas"]) >= max_escenas:
                    break
                datos["escenas"].append({
                    "id": len(datos["escenas"]),
                    **escena.model_dump(),
                    "imagen": None,
                    "prompt_imagen": None,
                    "segmentos": [{**s.model_dump(), "audio": None} for s in escena.segmentos],
                })
            guardar(ajustes, datos)

        personajes = _personajes(datos)
        ficha = FichaObra(**datos["ficha"])
        total = len(datos["escenas"])
        for escena in datos["escenas"]:
            _paso(ajustes, datos, "ilustrando", "Pintando las escenas", escena["id"] + 1, total)
            _ilustrar_escena(base, ficha, escena, personajes, ilustrador)
            guardar(ajustes, datos)

        if narrador is not None:
            pendientes = [(e, s) for e in datos["escenas"] for s in e["segmentos"]]
            for n, (escena, seg) in enumerate(pendientes, 1):
                _paso(ajustes, datos, "narrando", "Grabando las voces", n, len(pendientes))
                voz, indicaciones = indicaciones_voz(ficha, seg["hablante"], seg["emocion"], personajes)
                destino = base / "audio" / f"e{escena['id']:03d}_s{n:04d}"
                ruta = narrador.generar(seg["texto"], voz, indicaciones, destino)
                seg["audio"] = f"audio/{ruta.name}"
            guardar(ajustes, datos)

        _paso(ajustes, datos, "listo", "Listo para leer", total, total)
    except Exception as exc:  # se reporta al usuario en el lector
        datos["estado"] = "error"
        datos["error"] = _mensaje_error(exc)
        datos["detalle_error"] = traceback.format_exc(limit=3)
        guardar(ajustes, datos)
    return datos


def _mensaje_error(exc: Exception) -> str:
    nombre = exc.__class__.__name__
    if exc.__class__.__module__.startswith("openai"):
        if nombre == "AuthenticationError":
            return "La clave de OpenAI no es válida. Revísela en Configuración."
        if nombre == "RateLimitError":
            return "OpenAI indicó límite de uso o saldo insuficiente. Intente más tarde."
        return f"OpenAI respondió con un error: {exc}"
    return str(exc) or nombre


def _ilustrar_escena(base: Path, ficha: FichaObra, escena: dict, personajes, ilustrador) -> None:
    prompt = prompt_imagen(ficha, _escena_modelo(escena), personajes)
    destino = base / "img" / f"escena_{escena['id']:03d}_{int(time.time())}"
    if isinstance(ilustrador, IlustradorProvisional):
        ruta = ilustrador.generar(prompt, destino, titulo=escena["titulo"])
    else:
        ruta = ilustrador.generar(prompt, destino)
    escena["imagen"] = f"img/{ruta.name}"
    escena["prompt_imagen"] = prompt


def _escena_modelo(escena: dict):
    from .analizar import Escena, Segmento

    return Escena(
        titulo=escena["titulo"], descripcion_imagen=escena["descripcion_imagen"],
        personajes_presentes=escena["personajes_presentes"],
        segmentos=[Segmento(hablante=s["hablante"], texto=s["texto"], emocion=s["emocion"])
                   for s in escena["segmentos"]],
    )


def regenerar_imagen(ajustes: Ajustes, pid: str, indice: int, descripcion: str | None = None,
                     ilustrador=None) -> dict:
    datos = leer(ajustes, pid)
    escena = datos["escenas"][indice]
    if descripcion:
        escena["descripcion_imagen"] = descripcion
    ilustrador = ilustrador or _ilustrador(ajustes, datos["opciones"])
    anterior = escena.get("imagen")
    _ilustrar_escena(carpeta(ajustes, pid), FichaObra(**datos["ficha"]), escena,
                     _personajes(datos), ilustrador)
    if anterior and anterior != escena["imagen"]:
        (carpeta(ajustes, pid) / anterior).unlink(missing_ok=True)
    guardar(ajustes, datos)
    return escena


def procesar_en_segundo_plano(ajustes: Ajustes, pid: str) -> threading.Thread:
    hilo = threading.Thread(target=procesar, args=(ajustes, pid), daemon=True)
    hilo.start()
    return hilo
