"""Interfaz web del convertidor (se abre en el navegador).

    python -m psr_midi.web            -> http://localhost:8765
"""
from __future__ import annotations

import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .converter import VOCES_GM, configuracion_por_defecto, convertir
from .yamaha import nombre_archivo_seguro

app = FastAPI(title="Canción a MIDI - PSR-S950")
CARPETA = Path(tempfile.gettempdir()) / "psr_midi_web"
CARPETA.mkdir(exist_ok=True)
TRABAJOS: dict[str, dict] = {}

PISTAS = {
    "melodia": "Melodía de la voz (canal 1 · TRACK 1)",
    "acompanamiento": "Acordes / acompañamiento (canal 2 · TRACK 2)",
    "bajo": "Bajo (canal 3)",
    "agudos": "Instrumentos agudos: punteos, vientos (canal 4)",
    "bateria": "Batería / percusión (canal 10)",
}

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canción a MIDI · PSR-S950</title>
<style>
:root{--bg:#f4f1ea;--card:#fff;--ink:#1f2328;--muted:#5d6670;--acc:#8a1c2b;--line:#e2ddd2}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--card:#202329;--ink:#eceff3;--muted:#9aa3ad;--acc:#e0566a;--line:#33373e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:1.5rem;margin:.2em 0}p.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
label{display:block;font-weight:600;margin:12px 0 6px}
.drop{border:2px dashed var(--line);border-radius:12px;padding:28px 12px;text-align:center;cursor:pointer}
.drop.on{border-color:var(--acc)}.drop b{color:var(--acc)}
select,input[type=number]{width:100%;padding:10px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);font-size:1rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 12px}@media(max-width:480px){.grid{grid-template-columns:1fr}}
.grid label{font-weight:400;margin:4px 0}
button{width:100%;padding:14px;border:0;border-radius:10px;background:var(--acc);color:#fff;font-size:1.05rem;font-weight:700;cursor:pointer;margin-top:16px}
button:disabled{opacity:.5}
#log{white-space:pre-wrap;font:13px/1.4 ui-monospace,monospace;color:var(--muted);max-height:240px;overflow:auto}
a.dl{display:block;text-align:center;padding:14px;border-radius:10px;background:#1f7a3a;color:#fff;font-weight:700;text-decoration:none;margin-top:12px}
.nota{font-size:.9rem;color:var(--muted)}
</style></head><body><main>
<h1>🎹 Canción a MIDI</h1>
<p class="sub">Para Yamaha PSR-S950 · Suba un MP3 o MP4 y descargue el archivo .mid</p>
<form id="f" class="card">
  <div class="drop" id="drop">📂 <b>Toque aquí para elegir la canción</b><br><span id="nombre" class="nota">MP3, MP4, M4A, WAV…</span></div>
  <input type="file" id="archivo" name="archivo" accept="audio/*,video/*" hidden>
  <label>Ajuste rítmico</label>
  <select name="cuantizar"><option value="0">Tiempo exacto</option><option value="2">Corcheas</option><option value="4" selected>Semicorcheas</option></select>
  <label>Tempo (BPM) — vacío = automático</label>
  <input type="number" name="bpm" min="30" max="250" step="0.1" placeholder="Ej: 72">
  <label>Sonido de la melodía</label>
  <select name="voz">%VOCES%</select>
  <label>Sonido del acompañamiento</label>
  <select name="voz_acomp">%VOCES_ACOMP%</select>
  <label>Sonido de los instrumentos agudos</label>
  <select name="voz_agudos">%VOCES_AGUDOS%</select>
  <label>Instrumentos</label>
  <div class="grid">%PISTAS%</div>
  <button id="btn" type="submit">Convertir a MIDI</button>
  <p class="nota">%AVISO%</p>
</form>
<div class="card" id="estado" hidden><div id="log"></div><div id="res"></div></div>
</main><script>
const f=document.getElementById('f'),inp=document.getElementById('archivo'),drop=document.getElementById('drop');
drop.onclick=()=>inp.click();
inp.onchange=()=>{document.getElementById('nombre').textContent=inp.files[0]?inp.files[0].name:''};
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('on')}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('on')}));
drop.addEventListener('drop',ev=>{inp.files=ev.dataTransfer.files;inp.onchange()});
f.onsubmit=async ev=>{ev.preventDefault();
  if(!inp.files[0]){alert('Primero elija la canción');return}
  const btn=document.getElementById('btn');btn.disabled=true;btn.textContent='Subiendo…';
  const fd=new FormData(f);fd.set('archivo',inp.files[0]);
  const est=document.getElementById('estado'),log=document.getElementById('log'),res=document.getElementById('res');
  est.hidden=false;res.innerHTML='';log.textContent='Subiendo la canción…';
  const r=await fetch('api/convertir',{method:'POST',body:fd});const j=await r.json();
  btn.textContent='Convirtiendo… (puede tardar unos minutos)';
  const t=setInterval(async()=>{const s=await (await fetch('api/estado/'+j.id)).json();
    log.textContent=s.log.join('\\n');log.scrollTop=log.scrollHeight;
    if(s.listo||s.error){clearInterval(t);btn.disabled=false;btn.textContent='Convertir a MIDI';
      res.innerHTML=s.error?'<p style="color:var(--acc)">✘ '+s.error+'</p>':
      '<a class="dl" href="api/descargar/'+j.id+'">⬇ Descargar '+s.nombre+'</a><p class="nota">Cópielo a una memoria USB y ábralo en el teclado con SONG → USB.</p>'}},1000)};
</script></body></html>"""


def _pagina() -> str:
    from .mdx import mdx_disponible

    voces = "".join(
        f'<option value="{n}"{" selected" if n == "Flauta" else ""}>{n}</option>' for n in VOCES_GM
    )
    voces_acomp = "".join(
        f'<option value="{n}"{" selected" if n == "Piano de cola" else ""}>{n}</option>' for n in VOCES_GM
    )
    voces_agudos = "".join(
        f'<option value="{n}"{" selected" if n == "Guitarra eléctrica limpia" else ""}>{n}</option>' for n in VOCES_GM
    )
    pistas = "".join(
        f'<label><input type="checkbox" name="pistas" value="{k}" checked> {v}</label>' for k, v in PISTAS.items()
    )
    aviso = (
        "La voz se separa de los instrumentos con inteligencia artificial; los instrumentos se transcriben "
        "sin la voz para que el acompañamiento quede limpio."
        if mdx_disponible()
        else "Sin separación de voz: la melodía se toma de la línea más aguda de la mezcla."
    )
    return PAGINA.replace("%VOCES_AGUDOS%", voces_agudos).replace("%VOCES_ACOMP%", voces_acomp).replace("%VOCES%", voces).replace("%PISTAS%", pistas).replace("%AVISO%", aviso)


@app.get("/", response_class=HTMLResponse)
def inicio() -> str:
    return _pagina()


@app.post("/api/convertir")
async def api_convertir(
    archivo: UploadFile = File(...),
    cuantizar: int = Form(4),
    bpm: str = Form(""),
    voz: str = Form("Flauta"),
    voz_acomp: str = Form("Piano de cola"),
    voz_agudos: str = Form("Guitarra eléctrica limpia"),
    pistas: list[str] = Form(default=[]),
):
    id_ = uuid.uuid4().hex[:12]
    carpeta = CARPETA / id_
    carpeta.mkdir()
    original = Path(archivo.filename or "cancion.mp3")
    entrada = carpeta / ("entrada" + original.suffix.lower())
    entrada.write_bytes(await archivo.read())
    nombre = nombre_archivo_seguro(original.stem) + ".mid"

    config = configuracion_por_defecto()
    for clave, c in config.items():
        c.activo = clave in pistas
    config["melodia"].programa = VOCES_GM.get(voz, VOCES_GM["Flauta"])
    config["acompanamiento"].programa = VOCES_GM.get(voz_acomp, VOCES_GM["Piano de cola"])
    config["agudos"].programa = VOCES_GM.get(voz_agudos, VOCES_GM["Guitarra eléctrica limpia"])
    try:
        bpm_manual = float(bpm.replace(",", ".")) if bpm.strip() else None
    except ValueError:
        bpm_manual = None

    trabajo = {"log": [f"Canción recibida: {original.name}"], "listo": False, "error": None,
               "nombre": nombre, "ruta": str(carpeta / nombre)}
    TRABAJOS[id_] = trabajo

    def correr() -> None:
        try:
            convertir(entrada, carpeta / nombre, cuantizar=cuantizar or None, config=config,
                      bpm_manual=bpm_manual, log=trabajo["log"].append)
            trabajo["listo"] = True
        except Exception as exc:  # noqa: BLE001
            trabajo["error"] = str(exc)

    threading.Thread(target=correr, daemon=True).start()
    return {"id": id_}


@app.get("/api/estado/{id_}")
def api_estado(id_: str):
    t = TRABAJOS.get(id_)
    if not t:
        return JSONResponse({"error": "Trabajo no encontrado"}, status_code=404)
    return {k: t[k] for k in ("log", "listo", "error", "nombre")}


@app.get("/api/descargar/{id_}")
def api_descargar(id_: str):
    t = TRABAJOS.get(id_)
    if not t or not t["listo"]:
        return JSONResponse({"error": "Aún no está listo"}, status_code=404)
    return FileResponse(t["ruta"], media_type="audio/midi", filename=t["nombre"])


def main() -> None:
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PSR_PUERTO", "8765")))


if __name__ == "__main__":
    main()
