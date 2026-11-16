"""Separación voz / instrumentos con modelos MDX-Net (formato ONNX).

Funciona solo con numpy + onnxruntime (sin PyTorch), por lo que es liviano y
rápido. Modelo por defecto: ``UVR-MDX-NET-Voc_FT`` (proyecto Ultimate Vocal Remover).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

URL_MODELOS = "https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/"


@dataclass(frozen=True)
class ParamsMDX:
    archivo: str
    n_fft: int
    dim_f: int
    dim_t: int = 256
    hop: int = 1024
    compensar: float = 1.0
    pista_principal: str = "vocals"


MODELOS = {
    "voz": ParamsMDX("UVR-MDX-NET-Voc_FT.onnx", n_fft=7680, dim_f=3072, compensar=1.021),
}


def carpeta_modelos() -> Path:
    """Busca los modelos junto al programa; si no, en la carpeta del usuario."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    junto = base / "modelos"
    if junto.exists():
        return junto
    usuario = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "ConvertidorPSR" / "modelos"
    usuario.mkdir(parents=True, exist_ok=True)
    return usuario


def ruta_modelo(params: ParamsMDX, log: Callable[[str], None] = print) -> Path:
    for carpeta in (carpeta_modelos(), Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache")) / "ConvertidorPSR" / "modelos"):
        ruta = carpeta / params.archivo
        if ruta.exists():
            return ruta
    destino = carpeta_modelos() / params.archivo
    import urllib.request

    log(f"Descargando el modelo de IA {params.archivo} (~65 MB, solo la primera vez)...")
    tmp = destino.with_suffix(".part")
    urllib.request.urlretrieve(URL_MODELOS + params.archivo, tmp)
    tmp.replace(destino)
    return destino


def mdx_disponible() -> bool:
    import importlib.util

    return importlib.util.find_spec("onnxruntime") is not None


def _stft(x: np.ndarray, n_fft: int, hop: int, ventana: np.ndarray) -> np.ndarray:
    """STFT centrada (igual a torch.stft center=True, reflect). x: (canales, n) -> (canales, F, T)."""
    pad = n_fft // 2
    x = np.pad(x, ((0, 0), (pad, pad)), mode="reflect")
    n_frames = 1 + (x.shape[1] - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    marcos = x[:, idx] * ventana  # (c, T, n_fft)
    return np.fft.rfft(marcos, axis=-1).transpose(0, 2, 1)


def _istft(S: np.ndarray, n_fft: int, hop: int, ventana: np.ndarray, largo: int) -> np.ndarray:
    marcos = np.fft.irfft(S.transpose(0, 2, 1), n=n_fft, axis=-1) * ventana  # (c, T, n_fft)
    c, T, _ = marcos.shape
    total = n_fft + hop * (T - 1)
    salida = np.zeros((c, total))
    norma = np.zeros(total)
    v2 = ventana**2
    for t in range(T):
        salida[:, t * hop : t * hop + n_fft] += marcos[:, t]
        norma[t * hop : t * hop + n_fft] += v2
    salida /= np.maximum(norma, 1e-8)
    pad = n_fft // 2
    return salida[:, pad : pad + largo]


class SeparadorMDX:
    def __init__(self, params: ParamsMDX = MODELOS["voz"], log: Callable[[str], None] = print):
        import onnxruntime as ort

        self.p = params
        opciones = ort.SessionOptions()
        opciones.log_severity_level = 3
        self.sesion = ort.InferenceSession(
            str(ruta_modelo(params, log)), sess_options=opciones, providers=["CPUExecutionProvider"]
        )
        self.ventana = np.hanning(params.n_fft + 1)[:-1].astype(np.float32)  # Hann periódica
        self.trozo = params.hop * (params.dim_t - 1)

    def _espectro(self, x: np.ndarray) -> np.ndarray:
        S = _stft(x, self.p.n_fft, self.p.hop, self.ventana)[:, : self.p.dim_f]  # (2, F, T)
        return np.stack([S[0].real, S[0].imag, S[1].real, S[1].imag]).astype(np.float32)

    def _onda(self, E: np.ndarray, largo: int) -> np.ndarray:
        F = self.p.n_fft // 2 + 1
        S = np.zeros((2, F, E.shape[-1]), dtype=np.complex64)
        S[0, : self.p.dim_f] = E[0] + 1j * E[1]
        S[1, : self.p.dim_f] = E[2] + 1j * E[3]
        return _istft(S, self.p.n_fft, self.p.hop, self.ventana, largo)

    def separar(self, mezcla: np.ndarray, progreso: Callable[[float], None] | None = None) -> np.ndarray:
        """mezcla: (2, n) a 44.1 kHz. Devuelve la pista principal (voz) con la misma forma."""
        n = mezcla.shape[1]
        recorte = self.p.n_fft // 2
        util = self.trozo - 2 * recorte
        relleno = util - n % util
        x = np.concatenate(
            [np.zeros((2, recorte)), mezcla, np.zeros((2, relleno)), np.zeros((2, recorte))], axis=1
        ).astype(np.float32)
        partes = []
        inicios = list(range(0, n + relleno, util))
        for k, i in enumerate(inicios):
            bloque = x[:, i : i + self.trozo]
            E = self._espectro(bloque)[None]
            salida = self.sesion.run(None, {self.sesion.get_inputs()[0].name: E})[0][0]
            onda = self._onda(salida, self.trozo)
            partes.append(onda[:, recorte:-recorte])
            if progreso:
                progreso((k + 1) / len(inicios))
        voz = np.concatenate(partes, axis=1)[:, :n] * self.p.compensar
        return voz.astype(np.float32)
