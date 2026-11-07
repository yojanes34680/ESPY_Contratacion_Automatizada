"""Separación de la canción en pistas (stems) por instrumento.

Motor principal: Demucs (modelo ``htdemucs_6s`` de Meta), que separa en
voz, batería, bajo, piano, guitarra y "otros" (cuerdas, sintetizadores, órgano...).

Si Demucs no está instalado se usa un modo básico (sin IA) que divide la
mezcla en parte percusiva (batería), registro grave (bajo) y parte armónica.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.signal import butter, sosfiltfilt

from .audio_io import SAMPLE_RATE, cargar_audio, guardar_wav

STEMS_DEMUCS = ("vocals", "drums", "bass", "piano", "guitar", "other")


@dataclass
class Separacion:
    """Pistas separadas, todas mono a ``sr``."""

    sr: int
    mezcla: np.ndarray
    pistas: dict[str, np.ndarray] = field(default_factory=dict)
    motor: str = "basico"


def demucs_disponible() -> bool:
    return importlib.util.find_spec("demucs") is not None


def _filtro(y: np.ndarray, sr: int, tipo: str, corte: float, orden: int = 6) -> np.ndarray:
    sos = butter(orden, corte, btype=tipo, fs=sr, output="sos")
    return sosfiltfilt(sos, y).astype(np.float32)


def separar_basico(y: np.ndarray, sr: int = SAMPLE_RATE) -> Separacion:
    """Separación aproximada sin IA (HPSS + filtros)."""
    import librosa

    armonico, percusivo = librosa.effects.hpss(y, margin=(1.0, 2.0))
    bajo = _filtro(armonico, sr, "lowpass", 250.0)
    acordes = _filtro(armonico, sr, "highpass", 120.0, orden=4)
    return Separacion(
        sr=sr,
        mezcla=y,
        pistas={
            "drums": percusivo.astype(np.float32),
            "bass": bajo,
            "piano": acordes,
        },
        motor="basico",
    )


def separar_demucs(
    ruta: Path,
    sr: int = SAMPLE_RATE,
    modelo: str = "htdemucs_6s",
    dispositivo: str | None = None,
    log: Callable[[str], None] = print,
) -> Separacion:
    """Ejecuta Demucs en un proceso aparte y carga las pistas resultantes."""
    with tempfile.TemporaryDirectory(prefix="psr_midi_") as tmp:
        tmp = Path(tmp)
        wav = tmp / "cancion.wav"
        # Demucs trabaja a 44.1 kHz estéreo.
        guardar_wav(wav, cargar_audio(ruta, sr=44100, estereo=True), 44100)

        cmd = [sys.executable, "-m", "demucs", "-n", modelo, "-o", str(tmp / "sep"), str(wav)]
        if dispositivo:
            cmd += ["-d", dispositivo]
        log(f"Separando instrumentos con Demucs ({modelo}). Esto puede tardar varios minutos...")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError("Demucs falló:\n" + proc.stderr[-2000:])

        carpeta = tmp / "sep" / modelo / "cancion"
        pistas: dict[str, np.ndarray] = {}
        for nombre in STEMS_DEMUCS:
            archivo = carpeta / f"{nombre}.wav"
            if archivo.exists():
                pistas[nombre] = cargar_audio(archivo, sr=sr)
        if not pistas:
            raise RuntimeError(f"Demucs no generó pistas en {carpeta}")

    mezcla = cargar_audio(ruta, sr=sr)
    return Separacion(sr=sr, mezcla=mezcla, pistas=pistas, motor=f"demucs:{modelo}")


def separar(
    ruta: Path,
    usar_ia: bool = True,
    sr: int = SAMPLE_RATE,
    log: Callable[[str], None] = print,
    dispositivo: str | None = None,
) -> Separacion:
    if usar_ia and demucs_disponible():
        try:
            return separar_demucs(ruta, sr=sr, log=log, dispositivo=dispositivo)
        except Exception as exc:  # noqa: BLE001 - se informa y se continúa en modo básico
            log(f"Aviso: no se pudo usar Demucs ({exc}). Se usará el modo básico.")
    elif usar_ia:
        log("Aviso: Demucs no está instalado; se usará la separación básica (menos precisa).")
    y = cargar_audio(ruta, sr=sr)
    log("Separando percusión, bajo y armonía (modo básico)...")
    return separar_basico(y, sr)


def tiene_senal(y: np.ndarray, umbral_db: float = -45.0) -> bool:
    """Indica si una pista separada contiene algo audible (evita transcribir silencio)."""
    if y.size == 0:
        return False
    rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
    return 20 * np.log10(rms + 1e-12) > umbral_db
