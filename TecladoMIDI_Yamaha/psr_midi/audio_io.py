"""Lectura de audio desde cualquier formato (MP3, MP4, M4A, WAV, FLAC, OGG, video...).

Se usa ffmpeg para extraer la pista de audio, de modo que también funcionan
archivos de video como MP4, MKV o MOV.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

SAMPLE_RATE = 22050


def ffmpeg_disponible() -> bool:
    return shutil.which("ffmpeg") is not None


def cargar_audio(ruta: str | Path, sr: int = SAMPLE_RATE, estereo: bool = False) -> np.ndarray:
    """Devuelve el audio como float32.

    Forma: (n,) si es mono, (2, n) si estereo=True.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")

    canales = 2 if estereo else 1
    if ffmpeg_disponible():
        cmd = [
            "ffmpeg", "-v", "error", "-nostdin", "-i", str(ruta),
            "-vn", "-ac", str(canales), "-ar", str(sr), "-f", "f32le", "-",
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "ffmpeg no pudo leer el archivo: " + proc.stderr.decode(errors="ignore")
            )
        datos = np.frombuffer(proc.stdout, dtype=np.float32).copy()
        if estereo:
            datos = datos.reshape(-1, 2).T
        return datos

    # Sin ffmpeg: librosa/soundfile (sirve para WAV/FLAC/OGG y MP3 en muchos casos).
    import librosa

    y, _ = librosa.load(str(ruta), sr=sr, mono=not estereo)
    return y.astype(np.float32)


def guardar_wav(ruta: str | Path, y: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    import soundfile as sf

    datos = y.T if y.ndim == 2 else y
    sf.write(str(ruta), datos, sr)
