"""Escritura de archivos MIDI estándar (SMF) listos para el Yamaha PSR-S950.

El PSR-S950 reproduce archivos .MID (SMF formato 0 y 1) desde USB o memoria
interna, con sonidos GM/XG. Este módulo:

- Envía "GM System On" y "XG System On" al inicio para que el teclado se
  reinicie a un estado conocido.
- Asigna cada instrumento a su canal y voz (Program Change + Bank Select).
- Coloca la melodía en el canal 1 (botón [TRACK 1] del teclado) para poder
  silenciarla y cantarla/tocarla en vivo; el piano en el canal 2 ([TRACK 2]);
  el resto en canales 3-16 ([EXTRA TRACKS]); la batería en el canal 10.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import mido

from .transcription import Nota

PPQ = 480
GM_ON = [0x7E, 0x7F, 0x09, 0x01]
XG_ON = [0x43, 0x10, 0x4C, 0x00, 0x00, 0x7E, 0x00]


@dataclass
class Parte:
    """Un instrumento dentro de la secuencia."""

    nombre: str
    canal: int  # 0..15 (canal MIDI 1..16)
    programa: int  # 0..127 (número GM, base 0)
    notas: list[Nota] = field(default_factory=list)
    volumen: int = 100
    paneo: int = 64
    reverb: int = 40
    chorus: int = 0
    bateria: bool = False


def nombre_archivo_seguro(texto: str, max_len: int = 40) -> str:
    """Nombre ASCII sencillo, que el explorador de archivos del teclado muestra bien."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9 _-]+", "", t).strip().replace(" ", "_")
    return (t or "cancion")[:max_len]


def _a_ticks(segundos: float, bpm: float, desplazamiento: float) -> int:
    return int(round((segundos + desplazamiento) * bpm / 60.0 * PPQ))


def escribir_midi(
    partes: list[Parte],
    salida: str | Path,
    bpm: float = 120.0,
    titulo: str = "Cancion",
    primer_pulso: float | None = None,
    cuantizar: int | None = None,
    formato: int = 0,
    compas_entrada: bool = True,
) -> Path:
    """Escribe el archivo .mid.

    - ``primer_pulso``: segundo en que cae el primer pulso detectado; se usa para
      alinear la música con la cuadrícula de compases del teclado.
    - ``cuantizar``: divisiones por negra (4 = semicorcheas). ``None`` = tiempo exacto.
    - ``compas_entrada``: deja un compás de silencio inicial para que el teclado
      configure las voces antes de sonar.
    """
    salida = Path(salida)
    seg_por_pulso = 60.0 / bpm
    desplazamiento = 0.0
    if primer_pulso is not None and primer_pulso > 0:
        resto = primer_pulso % seg_por_pulso
        desplazamiento = (seg_por_pulso - resto) % seg_por_pulso
    if compas_entrada:
        desplazamiento += 4 * seg_por_pulso

    rejilla = PPQ // cuantizar if cuantizar else None

    # Lista de eventos (tick, prioridad, mensaje). Prioridad: 0 config, 1 note_off, 2 note_on.
    eventos: list[tuple[int, int, int, mido.Message | mido.MetaMessage]] = []
    orden = 0

    def agregar(tick: int, prioridad: int, msg) -> None:
        nonlocal orden
        eventos.append((tick, prioridad, orden, msg))
        orden += 1

    agregar(0, 0, mido.MetaMessage("track_name", name=titulo[:60]))
    agregar(0, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
    agregar(0, 0, mido.MetaMessage("time_signature", numerator=4, denominator=4))
    agregar(0, 0, mido.Message("sysex", data=GM_ON))
    agregar(PPQ // 8, 0, mido.Message("sysex", data=XG_ON))
    t_cfg = PPQ // 2  # el XG necesita ~50 ms tras el reset

    for parte in partes:
        c = parte.canal
        agregar(t_cfg, 0, mido.MetaMessage("text", text=f"Canal {c + 1}: {parte.nombre}"))
        agregar(t_cfg, 0, mido.Message("control_change", channel=c, control=0, value=127 if parte.bateria else 0))
        agregar(t_cfg, 0, mido.Message("control_change", channel=c, control=32, value=0))
        agregar(t_cfg, 0, mido.Message("program_change", channel=c, program=parte.programa))
        agregar(t_cfg, 0, mido.Message("control_change", channel=c, control=7, value=parte.volumen))
        agregar(t_cfg, 0, mido.Message("control_change", channel=c, control=10, value=parte.paneo))
        agregar(t_cfg, 0, mido.Message("control_change", channel=c, control=91, value=parte.reverb))
        agregar(t_cfg, 0, mido.Message("control_change", channel=c, control=93, value=parte.chorus))

        # Convertir a ticks y evitar solapamientos de la misma nota en el mismo canal.
        convertidas: list[tuple[int, int, int, int]] = []
        for n in parte.notas:
            if not 0 <= n.tono <= 127:
                continue
            ini = _a_ticks(n.inicio, bpm, desplazamiento)
            fin = _a_ticks(n.fin, bpm, desplazamiento)
            if rejilla:
                ini = int(round(ini / rejilla)) * rejilla
                fin = max(ini + rejilla, int(round(fin / rejilla)) * rejilla)
            fin = max(fin, ini + 10)
            convertidas.append((ini, fin, n.tono, int(max(1, min(127, n.velocidad)))))
        convertidas.sort()
        ultimo_por_tono: dict[int, int] = {}
        for idx, (ini, fin, tono, vel) in enumerate(convertidas):
            previo = ultimo_por_tono.get(tono)
            if previo is not None:
                p_ini, p_fin, _, p_vel = convertidas[previo]
                if p_fin > ini:
                    if ini <= p_ini:  # misma nota duplicada: conservar la más fuerte
                        convertidas[previo] = (p_ini, max(p_fin, fin), tono, max(p_vel, vel))
                        convertidas[idx] = (0, 0, -1, 0)
                        continue
                    convertidas[previo] = (p_ini, ini, tono, p_vel)
            ultimo_por_tono[tono] = idx
        for ini, fin, tono, vel in convertidas:
            if tono < 0 or fin <= ini:
                continue
            agregar(ini, 2, mido.Message("note_on", channel=c, note=tono, velocity=vel))
            agregar(fin, 1, mido.Message("note_off", channel=c, note=tono, velocity=0))

    eventos.sort(key=lambda e: (e[0], e[1], e[2]))
    fin_total = (eventos[-1][0] if eventos else 0) + PPQ

    def a_pista(lista) -> mido.MidiTrack:
        pista = mido.MidiTrack()
        anterior = 0
        for tick, _, _, msg in lista:
            pista.append(msg.copy(time=tick - anterior))
            anterior = tick
        pista.append(mido.MetaMessage("end_of_track", time=max(0, fin_total - anterior)))
        return pista

    mid = mido.MidiFile(type=formato, ticks_per_beat=PPQ)
    if formato == 0:
        mid.tracks.append(a_pista(eventos))
    else:
        globales = [e for e in eventos if not hasattr(e[3], "channel")]
        mid.tracks.append(a_pista(globales))
        for parte in partes:
            propios = [e for e in eventos if getattr(e[3], "channel", None) == parte.canal]
            pista = a_pista(propios)
            pista.insert(0, mido.MetaMessage("track_name", name=parte.nombre[:60], time=0))
            mid.tracks.append(pista)

    salida.parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(salida))
    return salida
