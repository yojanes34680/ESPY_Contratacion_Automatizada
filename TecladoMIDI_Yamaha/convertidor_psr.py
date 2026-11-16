"""Punto de entrada del programa para Windows (ConvertidorPSR.exe).

- Agrega al PATH el ffmpeg incluido junto al programa.
- Si la ventana no tiene consola, guarda los mensajes en un archivo de registro.
- ``--autoprueba salida.mid`` convierte una canción sintética sin abrir la
  ventana; se usa al construir el .exe para comprobar que todo quedó incluido.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _preparar_entorno() -> None:
    congelado = getattr(sys, "frozen", False)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    carpeta_exe = Path(sys.executable).parent if congelado else Path(__file__).resolve().parent
    for d in (base / "ffmpeg", carpeta_exe / "ffmpeg"):
        if (d / "ffmpeg.exe").exists() or (d / "ffmpeg").exists():
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
            break
    if sys.stdout is None or sys.stderr is None:  # ejecutable sin consola
        registro = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ConvertidorPSR" / "registro.txt"
        registro.parent.mkdir(parents=True, exist_ok=True)
        archivo = open(registro, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or archivo
        sys.stderr = sys.stderr or archivo


def _autoprueba(salida: Path) -> int:
    import subprocess
    import tempfile

    import numpy as np
    import soundfile as sf

    from psr_midi.audio_io import ffmpeg_disponible
    from psr_midi.converter import convertir

    try:
        sr = 44100
        t = np.arange(int(sr * 6)) / sr
        y = np.zeros_like(t)
        for k in range(10):  # acordes y bajo cada 0.6 s
            i = int(k * 0.6 * sr)
            tt = t[: int(0.55 * sr)]
            env = np.exp(-tt * 3)
            for f in (261.6, 329.6, 392.0, 65.4):
                y[i : i + tt.size] += 0.15 * np.sin(2 * np.pi * f * tt) * env
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "prueba.wav"
            sf.write(str(wav), (y / np.abs(y).max() * 0.8).astype(np.float32), sr)
            entrada = wav
            if ffmpeg_disponible():
                mp3 = Path(tmp) / "prueba.mp3"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), str(mp3)], check=True)
                entrada = mp3
            else:
                raise RuntimeError("ffmpeg no quedó incluido en el programa")
            # Proceso completo con IA: separación de voz (MDX) + Basic Pitch.
            res = convertir(entrada, salida, usar_ia=True, log=print)
        if res.motor_separacion != "mdx":
            raise RuntimeError(f"No se usó el separador de voz (motor: {res.motor_separacion})")
        from psr_midi.transcription import basic_pitch_disponible

        if not basic_pitch_disponible():
            raise RuntimeError("Basic Pitch no quedó incluido en el programa")
        print(f"AUTOPRUEBA OK: {res.archivo} {res.notas_por_parte}")
        return 0
    except Exception:  # noqa: BLE001
        Path(str(salida) + ".error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1


def main() -> int:
    _preparar_entorno()
    if len(sys.argv) >= 3 and sys.argv[1] == "--autoprueba":
        return _autoprueba(Path(sys.argv[2]))
    from psr_midi.gui import main as abrir_ventana

    abrir_ventana()
    return 0


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())
