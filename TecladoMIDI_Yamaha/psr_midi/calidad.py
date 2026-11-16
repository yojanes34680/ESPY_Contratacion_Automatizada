"""Medición objetiva de qué tan parecida es la secuencia a la canción original.

Compara, décima de segundo a décima de segundo, el croma (las 12 notas de la
escala que suenan) del audio original con el de las notas transcritas. 1.0 sería
idéntico; como referencia, notas al azar dan alrededor de 0.35.
"""
from __future__ import annotations

import numpy as np

from .transcription import Nota

FPS = 10


def croma_audio(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    import librosa

    hop = int(sr / FPS)
    C = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=hop)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0][: C.shape[1]]
    return C, rms


def croma_notas(notas: list[Nota], n_frames: int) -> np.ndarray:
    C = np.zeros((12, n_frames))
    for n in notas:
        i, j = max(int(n.inicio * FPS), 0), min(int(np.ceil(n.fin * FPS)), n_frames)
        if j > i:
            C[n.tono % 12, i:j] += n.velocidad / 127
    return C


def similitud(y: np.ndarray, sr: int, notas: list[Nota]) -> float:
    """Similitud media (0 a 1) entre el audio y las notas, en los momentos con sonido."""
    if not notas or y.size == 0:
        return 0.0
    A, rms = croma_audio(y, sr)
    B = croma_notas(notas, A.shape[1])
    mascara = rms > 0.1 * (rms.max() + 1e-12)
    num = (A * B).sum(0)
    den = np.linalg.norm(A, axis=0) * np.linalg.norm(B, axis=0) + 1e-9
    return float((num / den)[mascara].mean()) if mascara.any() else 0.0
