"""Servidor web local del Lector Ilustrado (FastAPI)."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import proyecto
from .config import RAIZ, cargar_ajustes, guardar_claves

WEB = RAIZ / "web"
TAMANO_MAXIMO = 80 * 1024 * 1024

def _marcar_interrumpidos() -> None:
    """Si el servidor se cerró a mitad de un proceso, lo deja marcado como error."""
    ajustes = cargar_ajustes()
    for p in proyecto.listar(ajustes):
        if p["estado"] not in ("listo", "error"):
            datos = proyecto.leer(ajustes, p["id"])
            datos["estado"] = "error"
            datos["error"] = "El proceso se interrumpió porque el programa se cerró."
            proyecto.guardar(ajustes, datos)


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI):
    _marcar_interrumpidos()
    yield


app = FastAPI(title="Lector Ilustrado", lifespan=_ciclo_de_vida)
app.mount("/web", StaticFiles(directory=WEB), name="web")


@app.get("/", response_class=HTMLResponse)
def inicio() -> str:
    return (WEB / "index.html").read_text(encoding="utf-8")


@app.get("/api/estado")
def estado() -> dict:
    a = cargar_ajustes()
    return {
        "tiene_claude": a.tiene_claude,
        "tiene_openai": a.tiene_openai,
        "modelo_texto": a.modelo_texto,
        "modelo_imagen": a.modelo_imagen,
        "modelo_voz": a.modelo_voz,
    }


@app.post("/api/claves")
def claves(datos: dict = Body(...)) -> dict:
    guardar_claves({k: v for k, v in datos.items() if isinstance(v, str)})
    return estado()


@app.get("/api/proyectos")
def proyectos() -> list[dict]:
    return proyecto.listar(cargar_ajustes())


@app.post("/api/proyectos")
async def crear_proyecto(archivo: UploadFile = File(...), opciones: str = Form("{}")) -> dict:
    nombre = archivo.filename or "documento.pdf"
    if Path(nombre).suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(400, "Solo se aceptan archivos PDF o TXT.")
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(400, "El archivo supera 80 MB.")
    try:
        op = json.loads(opciones or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "Opciones inválidas.")
    ajustes = cargar_ajustes()
    datos = proyecto.crear(ajustes, nombre, contenido, op)
    proyecto.procesar_en_segundo_plano(ajustes, datos["id"])
    return datos


def _leer_o_404(pid: str) -> dict:
    try:
        return proyecto.leer(cargar_ajustes(), pid)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Obra no encontrada.")


@app.get("/api/proyectos/{pid}")
def ver_proyecto(pid: str) -> dict:
    return _leer_o_404(pid)


@app.delete("/api/proyectos/{pid}")
def borrar_proyecto(pid: str) -> dict:
    _leer_o_404(pid)
    proyecto.eliminar(cargar_ajustes(), pid)
    return {"ok": True}


@app.post("/api/proyectos/{pid}/escenas/{indice}/imagen")
def nueva_imagen(pid: str, indice: int, datos: dict = Body(default={})) -> dict:
    p = _leer_o_404(pid)
    if not 0 <= indice < len(p["escenas"]):
        raise HTTPException(404, "Escena no encontrada.")
    try:
        return proyecto.regenerar_imagen(cargar_ajustes(), pid, indice, datos.get("descripcion"))
    except Exception as exc:
        raise HTTPException(400, proyecto._mensaje_error(exc))


@app.get("/medios/{pid}/{tipo}/{nombre}")
def medio(pid: str, tipo: str, nombre: str) -> FileResponse:
    if tipo not in ("img", "audio") or "/" in nombre or "\\" in nombre or nombre.startswith("."):
        raise HTTPException(404)
    try:
        ruta = proyecto.carpeta(cargar_ajustes(), pid) / tipo / nombre
    except ValueError:
        raise HTTPException(404)
    if not ruta.is_file():
        raise HTTPException(404)
    return FileResponse(ruta)


def main() -> None:
    import threading
    import webbrowser

    import uvicorn

    puerto = 8765
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{puerto}")).start()
    uvicorn.run(app, host="127.0.0.1", port=puerto)


if __name__ == "__main__":
    main()
