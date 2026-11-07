"""Uso por línea de comandos.

    python -m psr_midi.cli cancion.mp3
    python -m psr_midi.cli video.mp4 -o Alabanza.mid --cuantizar 4
"""
from __future__ import annotations

import argparse
import sys

from .converter import convertir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="psr_midi",
        description="Convierte una canción (MP3, MP4, WAV...) en una secuencia MIDI para Yamaha PSR-S950.",
    )
    ap.add_argument("entrada", help="Archivo de audio o video")
    ap.add_argument("-o", "--salida", help="Archivo .mid de salida (por defecto, junto a la canción)")
    ap.add_argument("--sin-ia", action="store_true", help="No usar Demucs/Basic Pitch (más rápido, menos preciso)")
    ap.add_argument(
        "--cuantizar", type=int, choices=[2, 4, 8], default=None,
        help="Ajustar notas a la cuadrícula: 2=corcheas, 4=semicorcheas, 8=fusas",
    )
    ap.add_argument("--formato", type=int, choices=[0, 1], default=0, help="SMF 0 (recomendado) o 1")
    ap.add_argument("--bpm", type=float, default=None, help="Forzar el tempo en lugar de detectarlo")
    ap.add_argument("--sin-melodia", action="store_true", help="No incluir la línea de la voz (canal 1)")
    ap.add_argument("--gpu", action="store_true", help="Usar la tarjeta gráfica NVIDIA para Demucs")
    args = ap.parse_args(argv)

    from .converter import configuracion_por_defecto

    config = configuracion_por_defecto()
    if args.sin_melodia:
        config["vocals"].activo = False

    try:
        res = convertir(
            args.entrada,
            args.salida,
            usar_ia=not args.sin_ia,
            cuantizar=args.cuantizar,
            formato=args.formato,
            config=config,
            bpm_manual=args.bpm,
            dispositivo="cuda" if args.gpu else None,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"\nArchivo creado: {res.archivo}  ({res.bpm:.1f} BPM)")
    for nombre, n in res.notas_por_parte.items():
        print(f"  {nombre}: {n} notas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
