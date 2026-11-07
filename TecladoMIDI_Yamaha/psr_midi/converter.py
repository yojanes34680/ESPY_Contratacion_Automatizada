"""Proceso completo: canción (MP3/MP4/...) -> secuencia MIDI para PSR-S950."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .audio_io import SAMPLE_RATE
from .drums import transcribir_bateria
from .separation import Separacion, separar, tiene_senal
from .transcription import transcribir_monofonico, transcribir_polifonico
from .yamaha import Parte, escribir_midi, nombre_archivo_seguro

# Voces GM (número base 0) con nombres en español, para la interfaz.
VOCES_GM = {
    "Piano de cola": 0,
    "Piano eléctrico": 4,
    "Órgano de iglesia": 19,
    "Órgano rock": 18,
    "Guitarra acústica (nylon)": 24,
    "Guitarra acústica (acero)": 25,
    "Guitarra eléctrica limpia": 27,
    "Guitarra distorsionada": 30,
    "Bajo eléctrico (dedos)": 33,
    "Bajo eléctrico (púa)": 34,
    "Violín": 40,
    "Cuerdas (ensamble)": 48,
    "Cuerdas lentas": 49,
    "Coro Aahs": 52,
    "Voz Oohs": 53,
    "Trompeta": 56,
    "Saxofón alto": 65,
    "Flauta": 73,
    "Sintetizador Pad cálido": 89,
}


@dataclass
class ConfigInstrumento:
    nombre: str
    canal: int
    programa: int
    tipo: str  # "poli", "mono" o "bateria"
    rango: tuple[int, int] = (21, 108)
    volumen: int = 100
    paneo: int = 64
    activo: bool = True


def configuracion_por_defecto() -> dict[str, ConfigInstrumento]:
    """Pista separada -> instrumento del teclado.

    Canal 1 = melodía ([TRACK 1]), canal 2 = piano ([TRACK 2]), canal 10 = batería.
    """
    return {
        "vocals": ConfigInstrumento("Melodia (voz)", 0, VOCES_GM["Flauta"], "mono", (48, 84), 90),
        "piano": ConfigInstrumento("Piano / acordes", 1, VOCES_GM["Piano de cola"], "poli", (21, 108), 95),
        "bass": ConfigInstrumento("Bajo", 2, VOCES_GM["Bajo eléctrico (dedos)"], "mono", (28, 62), 105),
        "guitar": ConfigInstrumento("Guitarra", 3, VOCES_GM["Guitarra acústica (acero)"], "poli", (40, 88), 85, 40),
        "other": ConfigInstrumento("Cuerdas / teclados", 4, VOCES_GM["Cuerdas (ensamble)"], "poli", (36, 96), 75, 88),
        "drums": ConfigInstrumento("Bateria", 9, 0, "bateria", (35, 81), 100),
    }


@dataclass
class Resultado:
    archivo: Path
    bpm: float
    motor_separacion: str
    notas_por_parte: dict[str, int] = field(default_factory=dict)


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

    modo_basico = sep.motor == "basico"
    bpm, primer_pulso = detectar_tempo(sep)
    if bpm_manual:
        bpm, primer_pulso = float(bpm_manual), None
    log(f"Tempo: {bpm:.1f} BPM")

    partes: list[Parte] = []
    conteo: dict[str, int] = {}
    for clave, y in sep.pistas.items():
        cfg = config.get(clave)
        if cfg is None or not cfg.activo:
            continue
        if not tiene_senal(y):
            log(f"  - {cfg.nombre}: sin sonido en la canción, se omite.")
            continue
        log(f"  - Transcribiendo {cfg.nombre}...")
        rango = cfg.rango
        if modo_basico and clave == "piano":
            rango = (max(rango[0], 43), rango[1])  # el bajo se transcribe aparte
        if cfg.tipo == "bateria":
            notas = transcribir_bateria(y, sep.sr, mezcla=sep.mezcla)
        elif cfg.tipo == "mono":
            notas = transcribir_monofonico(y, sep.sr, rango)
        else:
            notas = transcribir_polifonico(y, sep.sr, rango, usar_ia=usar_ia)
        conteo[cfg.nombre] = len(notas)
        log(f"      {len(notas)} notas")
        if notas:
            partes.append(
                Parte(
                    nombre=cfg.nombre,
                    canal=cfg.canal,
                    programa=cfg.programa,
                    notas=notas,
                    volumen=cfg.volumen,
                    paneo=cfg.paneo,
                    bateria=cfg.tipo == "bateria",
                )
            )

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
    return Resultado(archivo=salida, bpm=bpm, motor_separacion=sep.motor, notas_por_parte=conteo)
