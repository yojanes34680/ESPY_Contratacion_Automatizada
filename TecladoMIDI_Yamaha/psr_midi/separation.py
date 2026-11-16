"""Separación de la canción en pistas (stems) por instrumento.

Motor principal: Demucs (modelo ``htdemucs`` de Meta), que separa en
voz, batería, bajo y "otros" (acordeón, piano, guitarra, teclados, cuerdas...).

Si Demucs no está instalado se usa un modo básico (sin IA) que divide la
mezcla en parte percusiva (batería), registro grave (bajo) y parte armónica.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.signal import butter, sosfiltfilt

from .audio_io import SAMPLE_RATE, cargar_audio

STEMS_DEMUCS = ("vocals", "drums", "bass", "other")
MODELO_DEMUCS = "htdemucs"  # 4 pistas: la separación más limpia de Demucs


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
    """Separación aproximada sin IA: parte percusiva (batería) y parte armónica."""
    import librosa

    armonico, percusivo = librosa.effects.hpss(y, margin=(1.0, 2.0))
    return Separacion(
        sr=sr,
        mezcla=y,
        pistas={"drums": percusivo.astype(np.float32), "armonica": armonico.astype(np.float32)},
        motor="basico",
    )


def separar_demucs(
    ruta: Path,
    sr: int = SAMPLE_RATE,
    modelo: str = MODELO_DEMUCS,
    dispositivo: str | None = None,
    log: Callable[[str], None] = print,
) -> Separacion:
    """Ejecuta Demucs dentro del mismo proceso (funciona también en el .exe)."""
    import librosa
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    log(f"Cargando el modelo de IA {modelo} (la primera vez se descarga de Internet, ~80 MB)...")
    red = get_model(modelo)
    red.eval()
    if dispositivo is None:
        dispositivo = "cuda" if torch.cuda.is_available() else "cpu"

    audio = cargar_audio(ruta, sr=red.samplerate, estereo=True)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    wav = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
    ref = wav.mean(0)
    media, desv = ref.mean(), ref.std() + 1e-8
    log("Separando instrumentos con IA. Puede tardar varios minutos...")
    with torch.no_grad():
        fuentes = apply_model(red, ((wav - media) / desv)[None], device=dispositivo, split=True, overlap=0.25)[0]
    fuentes = fuentes * desv + media

    pistas: dict[str, np.ndarray] = {}
    for nombre, fuente in zip(red.sources, fuentes):
        mono = fuente.mean(0).cpu().numpy().astype(np.float32)
        pistas[nombre] = librosa.resample(mono, orig_sr=red.samplerate, target_sr=sr).astype(np.float32)
    mezcla = librosa.resample(audio.mean(0), orig_sr=red.samplerate, target_sr=sr).astype(np.float32)
    return Separacion(sr=sr, mezcla=mezcla, pistas=pistas, motor=f"demucs:{modelo}")


def separar_mdx(ruta: Path, sr: int = SAMPLE_RATE, log: Callable[[str], None] = print) -> Separacion:
    """Voz / instrumental con MDX-Net (ONNX); del instrumental se separan percusión y armonía."""
    import librosa

    from .mdx import SeparadorMDX

    estereo = cargar_audio(ruta, sr=44100, estereo=True)
    if estereo.ndim == 1:
        estereo = np.stack([estereo, estereo])
    separador = SeparadorMDX(log=log)
    log("Separando la voz de los instrumentos con IA (unos minutos)...")
    voz = separador.separar(estereo)
    instrumental = estereo - voz

    def a_mono(x: np.ndarray) -> np.ndarray:
        return librosa.resample(x.mean(0), orig_sr=44100, target_sr=sr).astype(np.float32)

    voz_m, inst_m, mezcla = a_mono(voz), a_mono(instrumental), a_mono(estereo)
    log("Separando percusión y armonía del instrumental...")
    armonica, percusiva = librosa.effects.hpss(inst_m, margin=(1.0, 2.0))
    return Separacion(
        sr=sr,
        mezcla=mezcla,
        pistas={
            "vocals": voz_m,
            "instrumental": inst_m,
            "armonica": armonica.astype(np.float32),
            "drums": percusiva.astype(np.float32),
        },
        motor="mdx",
    )


def separar(
    ruta: Path,
    usar_ia: bool = True,
    sr: int = SAMPLE_RATE,
    log: Callable[[str], None] = print,
    dispositivo: str | None = None,
) -> Separacion:
    from .mdx import mdx_disponible

    if usar_ia and mdx_disponible():
        try:
            return separar_mdx(ruta, sr=sr, log=log)
        except Exception as exc:  # noqa: BLE001 - se informa y se continúa
            log(f"Aviso: no se pudo separar la voz ({exc}).")
    if usar_ia and demucs_disponible():
        try:
            return separar_demucs(ruta, sr=sr, log=log, dispositivo=dispositivo)
        except Exception as exc:  # noqa: BLE001
            log(f"Aviso: no se pudo usar Demucs ({exc}).")
    y = cargar_audio(ruta, sr=sr)
    log("Separando percusión y armonía (modo básico, sin separar la voz)...")
    return separar_basico(y, sr)


def tiene_senal(y: np.ndarray, umbral_db: float = -45.0) -> bool:
    """Indica si una pista separada contiene algo audible (evita transcribir silencio)."""
    if y.size == 0:
        return False
    rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2)))
    return 20 * np.log10(rms + 1e-12) > umbral_db
