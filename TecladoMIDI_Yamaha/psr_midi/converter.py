"""Proceso completo: canción (MP3/MP4/...) -> secuencia MIDI para PSR-S950."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .audio_io import SAMPLE_RATE
from .drums import transcribir_bateria
from .separation import Separacion, separar, tiene_senal
from .calidad import similitud
from .transcription import (
    Nota,
    basic_pitch_disponible,
    linea_monofonica,
    transcribir_basic_pitch,
    transcribir_monofonico,
    transcribir_polifonico,
)
from .yamaha import Parte, escribir_midi, nombre_archivo_seguro

# Voces GM (número base 0) con nombres en español, para la interfaz.
VOCES_GM = {
    "Piano de cola": 0,
    "Piano brillante": 1,
    "Piano eléctrico": 4,
    "Órgano de iglesia": 19,
    "Órgano rock": 18,
    "Acordeón": 21,
    "Armónica": 22,
    "Guitarra acústica (nylon)": 24,
    "Guitarra acústica (acero)": 25,
    "Guitarra eléctrica limpia": 27,
    "Bajo acústico": 32,
    "Bajo eléctrico (dedos)": 33,
    "Bajo eléctrico (púa)": 34,
    "Violín": 40,
    "Cuerdas (ensamble)": 48,
    "Cuerdas lentas": 49,
    "Coro Aahs": 52,
    "Voz Oohs": 53,
    "Trompeta": 56,
    "Saxofón alto": 65,
    "Clarinete": 71,
    "Flauta": 73,
    "Sintetizador Pad cálido": 89,
}


@dataclass
class ConfigInstrumento:
    nombre: str
    canal: int
    programa: int
    volumen: int = 100
    paneo: int = 64
    activo: bool = True


def configuracion_por_defecto() -> dict[str, ConfigInstrumento]:
    """Partes de la secuencia y su lugar en el teclado.

    Canal 1 = melodía de la voz ([TRACK 1]), canal 2 = acordes ([TRACK 2]),
    canal 3 = bajo, canal 4 = instrumentos agudos (punteos, vientos),
    canal 10 = batería/percusión ([EXTRA TRACKS]).
    """
    return {
        "melodia": ConfigInstrumento("Melodia (voz)", 0, VOCES_GM["Flauta"], 95),
        "acompanamiento": ConfigInstrumento("Acompanamiento", 1, VOCES_GM["Piano de cola"], 90),
        "bajo": ConfigInstrumento("Bajo", 2, VOCES_GM["Bajo eléctrico (dedos)"], 105),
        "agudos": ConfigInstrumento("Instrumentos agudos", 3, VOCES_GM["Guitarra eléctrica limpia"], 80, 40),
        "bateria": ConfigInstrumento("Bateria", 9, 0, 95),
    }


@dataclass
class Resultado:
    archivo: Path
    bpm: float
    motor_separacion: str
    notas_por_parte: dict[str, int] = field(default_factory=dict)
    parecido: float = 0.0  # similitud armónica con la canción original (0 a 1)


def detectar_tempo(sep: Separacion) -> tuple[float, float | None]:
    """Devuelve (bpm, segundo del primer pulso)."""
    import librosa

    from .separation import _filtro

    hop = 256
    env = librosa.onset.onset_strength(y=sep.mezcla, sr=sep.sr, hop_length=hop, n_fft=512, n_mels=64)
    # Los graves (bombo y bajo) suelen marcar el pulso: se refuerzan para no
    # confundir el pulso con los contratiempos del hi-hat.
    graves = _filtro(sep.mezcla, sep.sr, "lowpass", 200.0, orden=4)
    env_graves = librosa.onset.onset_strength(y=graves, sr=sep.sr, hop_length=hop, n_fft=1024)[: len(env)]
    if env_graves.max() > 0:
        env = env / (env.max() + 1e-12) + 1.5 * env_graves / env_graves.max()
    tempo = librosa.feature.tempo(onset_envelope=env, sr=sep.sr, hop_length=hop)
    bpm = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 120.0
    if not np.isfinite(bpm) or bpm <= 0:
        bpm = 120.0
    while bpm < 65:
        bpm *= 2
    while bpm > 190:
        bpm /= 2
    return afinar_tempo_y_fase(env, sep.sr / hop, bpm)


def afinar_tempo_y_fase(env: np.ndarray, fps: float, bpm: float) -> tuple[float, float | None]:
    """Ajusta finamente el tempo (±3 %) y busca la fase de la cuadrícula de pulsos
    que mejor coincide con los ataques de la canción.

    Devuelve (bpm, segundo del primer pulso)."""
    if env.size < 4 or env.max() <= 0:
        return round(bpm, 2), None
    from scipy.ndimage import maximum_filter1d

    # Ensanchar los picos (±2 frames) para tolerar pequeñas imprecisiones.
    env = maximum_filter1d(env / env.max(), size=5)
    duracion = env.size / fps
    mejor = (-1.0, bpm, 0.0)
    for cand in np.arange(bpm * 0.97, bpm * 1.03, 0.05):
        periodo = 60.0 / cand
        fases = np.arange(0.0, periodo, 0.005)
        pulsos = fases[:, None] + np.arange(0.0, duracion - periodo, periodo)[None, :]
        idx = np.clip(np.round(pulsos * fps).astype(int), 0, env.size - 1)
        # Se premian los ataques en el pulso y un poco los de la mitad del pulso.
        medio = np.clip(np.round((pulsos + periodo / 2) * fps).astype(int), 0, env.size - 1)
        puntaje = env[idx].mean(axis=1) + 0.1 * env[medio].mean(axis=1)
        k = int(puntaje.argmax())
        if puntaje[k] > mejor[0]:
            mejor = (float(puntaje[k]), float(cand), float(fases[k]))
    return round(mejor[1], 2), mejor[2]


RANGO_MELODIA = (40, 84)  # cubre voces de hombre y de mujer
LIMITE_BAJO = 52  # por debajo de E3: bajo
LIMITE_AGUDOS = 72  # desde C5: instrumentos agudos (punteos, vientos)
CORTE_GRAVES_HZ = 170.0


def _transcribir(y: np.ndarray, sr: int, rango: tuple[int, int], usar_ia: bool, **umbrales) -> list[Nota]:
    if usar_ia and basic_pitch_disponible():
        return transcribir_basic_pitch(y, sr, rango, **umbrales)
    return transcribir_polifonico(y, sr, rango, usar_ia=False)


def quitar_armonicos(notas: list[Nota], solape: float = 0.6) -> list[Nota]:
    """Quita notas que son armónicos (octava, quinta sobre la octava...) de otra nota
    más fuerte que suena al mismo tiempo; típico error al transcribir una voz."""
    intervalos = {12, 19, 24, 28, 31}
    salida = []
    for n in notas:
        fantasma = False
        for m in notas:
            if m is n or (n.tono - m.tono) not in intervalos or m.velocidad < n.velocidad:
                continue
            comun = min(n.fin, m.fin) - max(n.inicio, m.inicio)
            if comun >= solape * n.duracion:
                fantasma = True
                break
        if not fantasma:
            salida.append(n)
    return salida


def transcribir_partes(
    sep: Separacion,
    usar_ia: bool = True,
    activas: set[str] | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, list[Nota]]:
    """Convierte las pistas separadas en melodía, acordes, bajo, agudos y batería.

    Lo medido con canciones reales: transcribir los instrumentos medios SIN los graves
    ni la percusión duplica la fidelidad del acompañamiento; el bajo sale mejor de la
    parte armónica completa.
    """
    from .separation import _filtro

    activas = activas if activas is not None else {"melodia", "acompanamiento", "bajo", "agudos", "bateria"}
    p = sep.pistas
    armonica = p.get("armonica", sep.mezcla)
    salida: dict[str, list[Nota]] = {}

    if "bajo" in activas:
        log("  - Transcribiendo el bajo...")
        if usar_ia and basic_pitch_disponible():
            graves = [n for n in transcribir_basic_pitch(armonica, sep.sr, (28, 64)) if n.tono < LIMITE_BAJO]
            salida["bajo"] = linea_monofonica(graves, aguda=False)
        else:  # sin red neuronal: seguimiento de tono (pYIN) sobre los graves filtrados
            solo_graves = _filtro(armonica, sep.sr, "lowpass", 250.0)
            salida["bajo"] = transcribir_monofonico(solo_graves, sep.sr, (28, LIMITE_BAJO + 8))

    log("  - Transcribiendo acordes e instrumentos...")
    sin_graves = _filtro(armonica, sep.sr, "highpass", CORTE_GRAVES_HZ)
    medios = _transcribir(sin_graves, sep.sr, (48, 96), usar_ia, umbral_ataque=0.4, umbral_nota=0.2)

    if "melodia" in activas:
        if "vocals" in p and tiene_senal(p["vocals"]):
            log("  - Transcribiendo la melodía de la voz...")
            voz = _transcribir(p["vocals"], sep.sr, RANGO_MELODIA, usar_ia, umbral_ataque=0.3, umbral_nota=0.2)
            salida["melodia"] = linea_monofonica(quitar_armonicos(voz), aguda=True, dur_min=0.08)
        else:
            # Sin la voz aislada, la línea más aguda es la mejor aproximación a la melodía.
            melodia = linea_monofonica([n for n in medios if n.tono >= 60], aguda=True, dur_min=0.1)
            salida["melodia"] = melodia
            clave = {(round(n.inicio, 3), n.tono) for n in melodia}
            medios = [n for n in medios if (round(n.inicio, 3), n.tono) not in clave]

    if "agudos" in activas:
        salida["agudos"] = [n for n in medios if n.tono >= LIMITE_AGUDOS]
        medios = [n for n in medios if n.tono < LIMITE_AGUDOS]
    if "acompanamiento" in activas:
        salida["acompanamiento"] = medios

    if "bateria" in activas and "drums" in p and tiene_senal(p["drums"]):
        log("  - Transcribiendo la batería y percusión...")
        salida["bateria"] = transcribir_bateria(p["drums"], sep.sr, mezcla=sep.mezcla)

    for clave, lista in salida.items():
        log(f"      {clave}: {len(lista)} notas")
    return salida


def convertir(
    entrada: str | Path,
    salida: str | Path | None = None,
    usar_ia: bool = True,
    cuantizar: int | None = None,
    formato: int = 0,
    config: dict[str, ConfigInstrumento] | None = None,
    bpm_manual: float | None = None,
    dispositivo: str | None = None,
    log: Callable[[str], None] = print,
) -> Resultado:
    entrada = Path(entrada)
    if salida is None:
        salida = entrada.with_name(nombre_archivo_seguro(entrada.stem) + ".mid")
    salida = Path(salida)
    config = config or configuracion_por_defecto()

    log(f"Leyendo: {entrada.name}")
    sep = separar(entrada, usar_ia=usar_ia, sr=SAMPLE_RATE, log=log, dispositivo=dispositivo)
    log(f"Pistas obtenidas ({sep.motor}): {', '.join(sep.pistas)}")

    bpm, primer_pulso = detectar_tempo(sep)
    if bpm_manual:
        bpm, primer_pulso = float(bpm_manual), None
    log(f"Tempo: {bpm:.1f} BPM")

    activas = {k for k, c in config.items() if c.activo}
    notas = transcribir_partes(sep, usar_ia=usar_ia, activas=activas, log=log)

    partes: list[Parte] = []
    conteo: dict[str, int] = {}
    for clave, lista in notas.items():
        cfg = config[clave]
        conteo[cfg.nombre] = len(lista)
        if lista and cfg.activo:
            partes.append(
                Parte(
                    nombre=cfg.nombre,
                    canal=cfg.canal,
                    programa=cfg.programa,
                    notas=lista,
                    volumen=cfg.volumen,
                    paneo=cfg.paneo,
                    bateria=clave == "bateria",
                )
            )

    tonales = [n for p in partes if not p.bateria for n in p.notas]
    parecido = similitud(sep.mezcla, sep.sr, tonales)
    log(f"Parecido armónico con la canción original: {parecido * 100:.0f} %")

    partes.sort(key=lambda p: p.canal)
    escribir_midi(
        partes,
        salida,
        bpm=bpm,
        titulo=entrada.stem,
        primer_pulso=primer_pulso,
        cuantizar=cuantizar,
        formato=formato,
    )
    log(f"Listo: {salida}")
    return Resultado(
        archivo=salida, bpm=bpm, motor_separacion=sep.motor, notas_por_parte=conteo, parecido=parecido
    )
