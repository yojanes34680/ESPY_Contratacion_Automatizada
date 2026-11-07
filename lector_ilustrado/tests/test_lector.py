"""Pruebas del Lector Ilustrado. No hacen llamadas a servicios externos."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from lector import config, proyecto
from lector.analizar import (AnalisisTramo, AnalistaBasico, Escena, FichaObra,
                             Personaje, Segmento, cobertura)
from lector.extraer import agrupar_en_tramos, armar_parrafos, leer_documento
from lector.medios import IlustradorProvisional, prompt_imagen, trocear_para_voz

CUENTO = """La tarde caía sobre el pueblo cuando Aurelio entró a la casa. Traía el sombrero lleno de polvo.

—¿Dónde está tu madre? —preguntó sin quitarse el sombrero.

—Se fue al río, papá —respondió Lucía desde la cocina.

El viejo se sentó junto a la ventana y miró el camino largo rato.

Afuera, los perros ladraban a las mulas que bajaban del monte.
"""


@pytest.fixture
def ajustes(tmp_path, monkeypatch):
    monkeypatch.setenv("LECTOR_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "ARCHIVO_ENV", tmp_path / ".env")
    return config.cargar_ajustes()


# ------------------------------------------------------------- extracción

def test_armar_parrafos_une_lineas_y_guiones():
    pagina = (
        "La tarde caía sobre el pueblo cuando Aurelio entró a la ca-\n"
        "sa con el sombrero lleno de polvo y las botas cubiertas de\n"
        "barro rojo del camino.\n"
        "—¿Dónde está tu madre?\n"
        "17\n"
    )
    parrafos = armar_parrafos([pagina])
    assert parrafos[0].startswith("La tarde caía")
    assert "casa con el sombrero" in parrafos[0]
    assert parrafos[0].endswith("camino.")
    assert parrafos[1] == "—¿Dónde está tu madre?"
    assert all("17" != p for p in parrafos)


def test_leer_pdf_real(tmp_path):
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    ruta = tmp_path / "cuento.pdf"
    c = canvas.Canvas(str(ruta))
    y = 800
    for linea in [
        "La tarde caia sobre el pueblo cuando Aurelio entro a la casa con el",
        "sombrero lleno de polvo y las botas cubiertas de barro.",
        "",
        "-Donde esta tu madre? -pregunto sin quitarse el sombrero.",
    ]:
        c.drawString(50, y, linea)
        y -= 16
    c.drawString(300, 40, "1")
    c.save()
    parrafos = leer_documento(ruta)
    assert len(parrafos) == 2
    assert "con el sombrero lleno" in parrafos[0]


def test_agrupar_en_tramos_respeta_limite():
    parrafos = ["palabra " * 100] * 10
    tramos = agrupar_en_tramos(parrafos, palabras_por_tramo=250)
    assert [len(t) for t in tramos] == [2, 2, 2, 2, 2]


# ------------------------------------------------------------- análisis

def test_analista_basico_separa_dialogos():
    parrafos = [p for p in CUENTO.split("\n\n") if p.strip()]
    analista = AnalistaBasico(parrafos_por_escena=3)
    ficha = analista.ficha(CUENTO)
    assert ficha.personajes and ficha.personajes[0].id == "personaje"
    resultado = analista.tramo(ficha, parrafos)
    assert len(resultado.escenas) == 2
    segs = resultado.escenas[0].segmentos
    assert segs[1].hablante == "personaje" and segs[1].texto == "¿Dónde está tu madre?"
    assert segs[2].hablante == "narrador" and segs[2].texto.startswith("preguntó")
    assert cobertura(parrafos, resultado) > 0.95


def test_analista_basico_puntuacion_tras_raya():
    from lector.analizar import _dividir_dialogo

    segs = _dividir_dialogo("—Se fue al río —respondió Lucía—. Dijo que volvía.")
    assert [(s.hablante, s.texto) for s in segs] == [
        ("personaje", "Se fue al río"),
        ("narrador", "respondió Lucía."),
        ("personaje", "Dijo que volvía."),
    ]


# ------------------------------------------------------------- medios

def _ficha() -> FichaObra:
    return FichaObra(
        titulo="La espera", autor="Anónimo", epoca="hacia 1920", lugar="Antioquia rural",
        contexto_historico="colonización cafetera", estilo_visual="acuarela costumbrista",
        paleta_colores="ocres y verdes", tono_narrador="pausado", voz_narrador="sage",
        personajes=[
            Personaje(id="aurelio", nombre="Aurelio", genero="masculino", edad_aproximada="60 años",
                      descripcion_fisica="flaco, bigote canoso", vestuario="ruana y sombrero aguadeño",
                      personalidad_voz="grave y cansada", voz="onyx"),
            Personaje(id="lucia", nombre="Lucía", genero="femenino", edad_aproximada="10 años",
                      descripcion_fisica="trenzas negras", vestuario="vestido de algodón",
                      personalidad_voz="aguda y tímida", voz="coral"),
        ],
    )


def test_prompt_imagen_incluye_epoca_y_personajes():
    ficha = _ficha()
    escena = Escena(titulo="Llegada", descripcion_imagen="Aurelio entra a la casa al atardecer",
                    personajes_presentes=["aurelio"], segmentos=[])
    prompt = prompt_imagen(ficha, escena, {p.id: p for p in ficha.personajes})
    assert "acuarela costumbrista" in prompt
    assert "Antioquia rural" in prompt
    assert "bigote canoso" in prompt and "ruana" in prompt
    assert "trenzas" not in prompt  # Lucía no está en la escena
    assert "Sin textos" in prompt


def test_trocear_para_voz():
    texto = "Una oración corta. " * 400
    trozos = trocear_para_voz(texto, limite=500)
    assert all(len(t) <= 500 for t in trozos)
    assert " ".join(trozos).split() == texto.split()


# ------------------------------------------------------------- flujo completo

class AnalistaFalso:
    def ficha(self, texto):
        return _ficha()

    def tramo(self, ficha, parrafos):
        return AnalisisTramo(
            personajes_nuevos=[Personaje(id="perro", nombre="Perro", genero="", edad_aproximada="",
                                         descripcion_fisica="", vestuario="", personalidad_voz="",
                                         voz="echo")],
            escenas=[Escena(
                titulo="Llegada", descripcion_imagen="Aurelio en la puerta",
                personajes_presentes=["aurelio", "lucia"],
                segmentos=[Segmento(hablante="narrador", texto=" ".join(parrafos), emocion="sereno")],
            )],
        )


class NarradorFalso:
    def __init__(self):
        self.llamadas = []

    def generar(self, texto, voz, indicaciones, destino: Path) -> Path:
        self.llamadas.append((voz, indicaciones))
        destino = destino.with_suffix(".mp3")
        destino.write_bytes(b"ID3")
        return destino


def test_procesar_flujo_completo(ajustes):
    datos = proyecto.crear(ajustes, "cuento.txt", CUENTO.encode(), {"max_escenas": 5})
    narrador = NarradorFalso()
    final = proyecto.procesar(ajustes, datos["id"], AnalistaFalso(), IlustradorProvisional(), narrador)
    assert final["estado"] == "listo", final.get("error")
    assert final["ficha"]["titulo"] == "La espera"
    assert any(p["id"] == "perro" for p in final["ficha"]["personajes"])
    escena = final["escenas"][0]
    base = proyecto.carpeta(ajustes, datos["id"])
    assert (base / escena["imagen"]).exists()
    assert (base / escena["segmentos"][0]["audio"]).exists()
    assert narrador.llamadas[0][0] == "sage"  # voz del narrador según la ficha
    assert proyecto.listar(ajustes)[0]["titulo"] == "La espera"


def test_procesar_sin_clave_reporta_error_claro(ajustes):
    datos = proyecto.crear(ajustes, "cuento.txt", CUENTO.encode(), {"analisis": "claude"})
    final = proyecto.procesar(ajustes, datos["id"])
    assert final["estado"] == "error"
    assert "Anthropic" in final["error"]


def test_guardar_claves(ajustes):
    config.guardar_claves({"OPENAI_API_KEY": "sk-prueba", "OTRA": "x"})
    texto = config.ARCHIVO_ENV.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=sk-prueba" in texto and "OTRA" not in texto
    config.guardar_claves({"OPENAI_API_KEY": ""})
    assert "OPENAI_API_KEY" not in config.ARCHIVO_ENV.read_text(encoding="utf-8")


# ------------------------------------------------------------- servidor

def test_api_modo_gratuito(ajustes):
    from fastapi.testclient import TestClient

    from lector.servidor import app

    cliente = TestClient(app)
    assert cliente.get("/").status_code == 200
    assert cliente.get("/api/estado").json()["tiene_claude"] is False

    opciones = '{"analisis": "basico", "imagenes": "provisional", "voces": "navegador"}'
    r = cliente.post("/api/proyectos", files={"archivo": ("cuento.txt", CUENTO.encode(), "text/plain")},
                     data={"opciones": opciones})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    for _ in range(50):
        datos = cliente.get(f"/api/proyectos/{pid}").json()
        if datos["estado"] in ("listo", "error"):
            break
        time.sleep(0.1)
    assert datos["estado"] == "listo", datos.get("error")
    assert datos["ficha"]["titulo"] == "cuento"
    imagen = datos["escenas"][0]["imagen"]
    assert cliente.get(f"/medios/{pid}/{imagen}").status_code == 200
    assert cliente.get(f"/medios/{pid}/img/..%2Fproyecto.json").status_code == 404
    assert cliente.get("/api/proyectos/no-existe").status_code == 404

    r = cliente.post("/api/proyectos", files={"archivo": ("virus.exe", b"x", "application/octet-stream")})
    assert r.status_code == 400

    assert cliente.post(f"/api/proyectos/{pid}/escenas/0/imagen", json={"descripcion": "Nueva"}).status_code == 200
    assert cliente.delete(f"/api/proyectos/{pid}").json() == {"ok": True}
    assert cliente.get("/api/proyectos").json() == []


def test_dialogo_con_guion_corto():
    from lector.analizar import _dividir_dialogo

    segs = _dividir_dialogo("-Ahí dentro se ha caído algo- dijo el apoderado en la habitación contigua.")
    assert [(s.hablante, s.texto) for s in segs] == [
        ("personaje", "Ahí dentro se ha caído algo"),
        ("narrador", "dijo el apoderado en la habitación contigua."),
    ]
    # un guion entre dos palabras no corta el diálogo
    segs = _dividir_dialogo("-Es un acuerdo franco-alemán -dijo.")
    assert segs[0].texto == "Es un acuerdo franco-alemán"


def test_pdf_omite_portada_y_titulos(tmp_path):
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    ruta = tmp_path / "libro.pdf"
    c = canvas.Canvas(str(ruta))
    c.drawString(50, 800, "LIBRO DESCARGADO EN WWW EJEMPLO COM")
    c.drawString(50, 780, "LA METAMORFOSIS")
    c.showPage()
    c.drawString(50, 800, "CAPITULO 1")
    c.drawString(50, 770, "Cuando Gregorio Samsa se desperto una manana despues de un sueno")
    c.drawString(50, 754, "intranquilo, se encontro sobre su cama convertido en un insecto.")
    c.save()
    parrafos = leer_documento(ruta)
    assert parrafos == ["Cuando Gregorio Samsa se desperto una manana despues de un sueno "
                        "intranquilo, se encontro sobre su cama convertido en un insecto."]
