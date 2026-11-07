"""Transcripción de batería: detecta golpes y los clasifica en bombo, redoblante,
hi-hat (cerrado/abierto) y platillo, usando las notas del mapa de batería GM/XG
que el PSR-S950 entiende en el canal 10."""
from __future__ import annotations

import numpy as np

from .transcription import Nota

BOMBO = 36
REDOBLANTE = 38
HIHAT_CERRADO = 42
HIHAT_ABIERTO = 46
PLATILLO = 49

_BANDAS = {"grave": (30, 150), "medio": (150, 2000), "agudo": (6000, 11000)}


def transcribir_bateria(
    y: np.ndarray, sr: int, hop: int = 256, mezcla: np.ndarray | None = None
) -> list[Nota]:
    """``mezcla`` (opcional): audio original, usado para precisar el instante de cada
    golpe, ya que la separación puede adelantar o atrasar levemente los ataques."""
    import librosa

    if y.size == 0 or np.max(np.abs(y)) < 1e-6:
        return []
    # Silencio inicial para poder detectar un golpe en el segundo 0.
    relleno = int(0.2 * sr)
    y = np.concatenate([np.zeros(relleno, dtype=y.dtype), y])
    n_fft = 2048
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    bandas = {
        k: S[(freqs >= a) & (freqs < b)].sum(axis=0) + 1e-12 for k, (a, b) in _BANDAS.items()
    }

    # Ventana corta (512) para que el instante del golpe sea preciso (~12 ms).
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, n_fft=512, n_mels=64)
    onsets = librosa.onset.onset_detect(
        onset_envelope=env, sr=sr, hop_length=hop, units="frames", backtrack=False, delta=0.08
    )
    if len(onsets) == 0:
        return []
    # Un mismo golpe a veces genera dos ataques muy seguidos (p. ej. el bombo):
    # se fusionan los que están a menos de 80 ms.
    separacion_min = max(1, int(0.08 * sr / hop))
    fusionados = [int(onsets[0])]
    for o in onsets[1:]:
        if o - fusionados[-1] >= separacion_min:
            fusionados.append(int(o))
    onsets = np.array(fusionados)

    if mezcla is not None and mezcla.size:
        m = np.concatenate([np.zeros(relleno, dtype=mezcla.dtype), mezcla])
        env_m = librosa.onset.onset_strength(y=m, sr=sr, hop_length=hop, n_fft=512, n_mels=64)
        radio = max(1, int(0.07 * sr / hop))
        precisos = []
        for o in onsets:
            a, b = max(0, o - radio), min(env_m.size, o + radio + 1)
            precisos.append(a + int(np.argmax(env_m[a:b])) if b > a else int(o))
        onsets = np.unique(np.array(precisos))

    ventana = max(1, int(0.07 * sr / hop))  # 70 ms tras el golpe
    energia = {k: np.array([v[o : o + ventana].sum() for o in onsets]) for k, v in bandas.items()}
    # Nivel típico de cada banda en los golpes, para comparar de forma relativa.
    referencia = {k: np.percentile(v, 75) + 1e-12 for k, v in energia.items()}
    total = sum(energia.values())
    total_db = 10 * np.log10(total / total.max())

    t = hop / sr
    notas: list[Nota] = []
    for i, o in enumerate(onsets):
        inicio = max(0.0, o * t - relleno / sr)
        vel = int(np.clip(40 + (total_db[i] + 30) / 30 * 85, 30, 127))
        rel = {k: energia[k][i] / referencia[k] for k in energia}
        golpes: list[int] = []
        if rel["grave"] > 0.5 and energia["grave"][i] > 0.6 * energia["medio"][i]:
            golpes.append(BOMBO)
        if rel["medio"] > 0.6 and energia["medio"][i] > 0.4 * energia["grave"][i]:
            golpes.append(REDOBLANTE)
        if rel["agudo"] > 0.4:
            # ¿El agudo se sostiene? -> hi-hat abierto o platillo.
            cola = bandas["agudo"][o + ventana : o + 4 * ventana].mean() if o + ventana < S.shape[1] else 0
            pico = bandas["agudo"][o : o + ventana].mean()
            sostenido = cola > 0.45 * pico
            if sostenido and rel["agudo"] > 1.8:
                golpes.append(PLATILLO)
            elif sostenido:
                golpes.append(HIHAT_ABIERTO)
            else:
                golpes.append(HIHAT_CERRADO)
        if not golpes:
            golpes.append(HIHAT_CERRADO if rel["agudo"] >= rel["grave"] else BOMBO)
        for g in golpes:
            notas.append(Nota(inicio, inicio + 0.1, g, vel))
    return notas
