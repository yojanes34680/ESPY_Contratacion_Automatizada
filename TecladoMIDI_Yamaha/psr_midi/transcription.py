"""Transcripción de audio a notas MIDI.

- ``transcribir_polifonico``: para piano, guitarra, cuerdas (varias notas a la vez).
  Usa Basic Pitch (Spotify) si está instalado; si no, un motor propio basado en
  la transformada Constant-Q con supresión de armónicos.
- ``transcribir_monofonico``: para voz principal y bajo (una nota a la vez),
  usando el algoritmo pYIN.
"""
from __future__ import annotations

import importlib.util
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter

HOP = 256
MIDI_MIN_88 = 21  # A0
MIDI_MAX_88 = 108  # C8


@dataclass
class Nota:
    inicio: float  # segundos
    fin: float  # segundos
    tono: int  # número de nota MIDI
    velocidad: int  # 1..127

    @property
    def duracion(self) -> float:
        return self.fin - self.inicio


def basic_pitch_disponible() -> bool:
    return importlib.util.find_spec("basic_pitch") is not None


def _velocidad_desde_db(db: float, piso: float = -45.0) -> int:
    """Convierte un nivel en dB (0 = máximo de la pista) a velocidad MIDI."""
    x = np.clip((db - piso) / (0.0 - piso), 0.0, 1.0)
    return int(round(35 + x * 80))


# ---------------------------------------------------------------------------
# Seguimiento de notas a partir de un "piano roll" (frames x tonos)
# ---------------------------------------------------------------------------
def _rachas(activo: np.ndarray) -> list[tuple[int, int]]:
    """Devuelve [(inicio, fin_exclusivo)] de las secuencias True de un vector booleano."""
    if not activo.any():
        return []
    d = np.diff(np.concatenate(([0], activo.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def notas_desde_roll(
    activo: np.ndarray,
    nivel_db: np.ndarray,
    tono_base: int,
    sr: int,
    hop: int,
    min_frames: int = 4,
    reataque_db: float = 6.0,
) -> list[Nota]:
    """Convierte una matriz booleana (frames x tonos) en notas.

    ``nivel_db`` tiene la misma forma y sirve para la velocidad y para detectar
    re-ataques (la misma nota tocada dos veces seguidas).
    """
    t = hop / sr
    notas: list[Nota] = []
    activo = median_filter(activo.astype(np.uint8), size=(3, 1)).astype(bool)
    for j in range(activo.shape[1]):
        for a, b in _rachas(activo[:, j]):
            segmento = nivel_db[a:b, j]
            # Partir la racha donde el nivel sube bruscamente (nuevo golpe de la misma nota).
            # (se compara contra 3 frames atrás porque el ataque tarda unos milisegundos).
            subida = segmento[3:] - segmento[:-3] if segmento.size > 3 else np.array([])
            picos = np.flatnonzero(subida > reataque_db) + 3
            cortes = [0]
            for c in picos:  # un corte por ataque, no varios seguidos
                if c - cortes[-1] >= min_frames:
                    cortes.append(int(c))
            cortes.append(b - a)
            for c0, c1 in zip(cortes[:-1], cortes[1:]):
                if c1 - c0 < min_frames:
                    continue
                db = float(np.max(segmento[c0:c1]))
                notas.append(
                    Nota(
                        inicio=(a + c0) * t,
                        fin=(a + c1) * t,
                        tono=tono_base + j,
                        velocidad=_velocidad_desde_db(db),
                    )
                )
    notas.sort(key=lambda n: (n.inicio, n.tono))
    return _filtrar_fantasmas(notas)


def _filtrar_fantasmas(notas: list[Nota], dur_max: float = 0.2, margen_vel: int = 12) -> list[Nota]:
    """Elimina notas cortas y débiles que aparecen junto al ataque de notas fuertes
    (artefacto típico del análisis espectral en el instante del golpe)."""
    if not notas:
        return notas
    inicios = np.array([n.inicio for n in notas])
    fines = np.array([n.fin for n in notas])
    vels = np.array([n.velocidad for n in notas])
    largos = np.array([n.duracion > dur_max for n in notas])
    salida = []
    for n in notas:
        if n.duracion > dur_max:
            salida.append(n)
            continue
        solapan = (inicios < n.fin) & (fines > n.inicio) & largos
        if solapan.any() and vels[solapan].max() - n.velocidad >= margen_vel:
            continue
        salida.append(n)
    return salida


# ---------------------------------------------------------------------------
# Motor polifónico propio (sin IA)
# ---------------------------------------------------------------------------
def _espectro_semitonos(y: np.ndarray, sr: int, hop: int) -> np.ndarray:
    """Magnitud CQT reducida a 88 semitonos (A0..C8). Forma (frames, 88)."""
    import librosa

    bpo = 36  # 3 bins por semitono
    fmin = librosa.midi_to_hz(MIDI_MIN_88) * 2 ** (-1 / bpo)
    C = np.abs(
        librosa.cqt(y, sr=sr, hop_length=hop, fmin=fmin, n_bins=88 * 3, bins_per_octave=bpo)
    )
    return C.reshape(88, 3, -1).max(axis=1).T.astype(np.float32)


def transcribir_polifonico_propio(
    y: np.ndarray,
    sr: int,
    rango: tuple[int, int] = (MIDI_MIN_88, MIDI_MAX_88),
    max_polifonia: int = 6,
    umbral_db: float = -40.0,
    rel_frame_db: float = -24.0,
) -> list[Nota]:
    S = _espectro_semitonos(y, sr, HOP)
    if S.size == 0 or S.max() <= 0:
        return []
    S = S / S.max()
    nivel_db = 20 * np.log10(S + 1e-9)
    restante = S.copy()
    n_frames, n_tonos = S.shape
    activo = np.zeros_like(S, dtype=bool)

    lo, hi = rango[0] - MIDI_MIN_88, rango[1] - MIDI_MIN_88
    umbral = 10 ** (umbral_db / 20)
    max_frame = S.max(axis=1)
    rel = 10 ** (rel_frame_db / 20)
    armonicos = [(int(round(12 * np.log2(h))), 0.9 ** (h - 1)) for h in range(1, 9)]
    filas = np.arange(n_frames)

    for _ in range(max_polifonia):
        # Puntuación: energía propia + apoyo de sus armónicos (limitado por la propia energía).
        puntaje = restante.copy()
        for off, w in armonicos[1:]:
            apoyo = np.zeros_like(restante)
            apoyo[:, : n_tonos - off] = restante[:, off:]
            puntaje += 0.5 * w * np.minimum(apoyo, restante)
        puntaje[:, :lo] = 0
        puntaje[:, hi + 1 :] = 0
        p = puntaje.argmax(axis=1)
        v = restante[filas, p]
        ok = (v > umbral) & (v > rel * max_frame)
        if not ok.any():
            break
        activo[filas[ok], p[ok]] = True
        # Suprimir la fundamental elegida y sus armónicos.
        for off, w in armonicos:
            idx = p + off
            valido = ok & (idx < n_tonos)
            r, c = filas[valido], idx[valido]
            restante[r, c] = np.maximum(restante[r, c] - v[valido] * (1.2 if off == 0 else w), 0)
        restante[filas[ok], np.clip(p[ok] - 1, 0, n_tonos - 1)] *= 0.5
        restante[filas[ok], np.clip(p[ok] + 1, 0, n_tonos - 1)] *= 0.5

    return notas_desde_roll(activo, nivel_db, MIDI_MIN_88, sr, HOP)


def transcribir_basic_pitch(y: np.ndarray, sr: int, rango: tuple[int, int]) -> list[Nota]:
    import librosa
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    from .audio_io import guardar_wav

    with tempfile.TemporaryDirectory(prefix="psr_bp_") as tmp:
        wav = Path(tmp) / "pista.wav"
        guardar_wav(wav, y, sr)
        _, _, eventos = predict(
            str(wav),
            ICASSP_2022_MODEL_PATH,
            minimum_frequency=float(librosa.midi_to_hz(rango[0])),
            maximum_frequency=float(librosa.midi_to_hz(rango[1])),
        )
    notas = [
        Nota(float(e[0]), float(e[1]), int(e[2]), int(np.clip(round(float(e[3]) * 127), 1, 127)))
        for e in eventos
        if rango[0] <= int(e[2]) <= rango[1]
    ]
    notas.sort(key=lambda n: (n.inicio, n.tono))
    return notas


def transcribir_polifonico(
    y: np.ndarray, sr: int, rango: tuple[int, int] = (MIDI_MIN_88, MIDI_MAX_88), usar_ia: bool = True
) -> list[Nota]:
    if usar_ia and basic_pitch_disponible():
        try:
            return transcribir_basic_pitch(y, sr, rango)
        except Exception:  # noqa: BLE001 - si falla la IA se usa el motor propio
            pass
    return transcribir_polifonico_propio(y, sr, rango)


# ---------------------------------------------------------------------------
# Motor monofónico (voz, bajo)
# ---------------------------------------------------------------------------
def transcribir_monofonico(
    y: np.ndarray,
    sr: int,
    rango: tuple[int, int],
    min_dur: float = 0.08,
    hop: int = 512,
) -> list[Nota]:
    import librosa

    fmin, fmax = librosa.midi_to_hz(rango[0]), librosa.midi_to_hz(rango[1])
    f0, voiced, _ = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr, frame_length=2048 if rango[0] >= 40 else 4096, hop_length=hop
    )
    n = len(f0)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0][:n]
    rms_db = 20 * np.log10(rms / (rms.max() + 1e-12) + 1e-9)

    tonos = np.where(voiced & np.isfinite(f0), np.round(librosa.hz_to_midi(np.nan_to_num(f0, nan=1.0))), 0)
    tonos = median_filter(tonos.astype(np.int32), size=5)  # quita parpadeos del vibrato
    tonos[rms_db < -50] = 0

    candidatos = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop, backtrack=True, units="frames")
    # Solo se acepta un ataque si el volumen realmente sube (evita cortar una nota
    # larga por ruido de otros instrumentos que se filtró en la pista).
    onsets = {
        int(o)
        for o in candidatos
        if rms_db[min(o + 3, n - 1)] - rms_db[max(o - 1, 0)] > 3.0
    }
    t = hop / sr
    notas: list[Nota] = []
    i = 0
    while i < n:
        p = tonos[i]
        if p <= 0:
            i += 1
            continue
        j = i + 1
        while j < n and tonos[j] == p and j not in onsets:
            j += 1
        if (j - i) * t >= min_dur:
            notas.append(Nota(i * t, j * t, int(p), _velocidad_desde_db(float(rms_db[i:j].max()))))
        i = j
    return notas
