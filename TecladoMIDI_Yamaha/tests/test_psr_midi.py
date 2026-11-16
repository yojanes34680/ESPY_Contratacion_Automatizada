"""Pruebas del convertidor canción -> MIDI para Yamaha PSR-S950.

Se usan señales sintéticas (tonos y golpes generados) para conocer de antemano
la respuesta correcta."""
from __future__ import annotations

from collections import defaultdict

import mido
import numpy as np
import pytest

from psr_midi.converter import afinar_tempo_y_fase, convertir
from psr_midi.drums import BOMBO, transcribir_bateria
from psr_midi.transcription import Nota, linea_monofonica, transcribir_monofonico, transcribir_polifonico_propio
from psr_midi.yamaha import GM_ON, PPQ, XG_ON, Parte, escribir_midi, nombre_archivo_seguro

SR = 22050


def _tono(y, midi, t0, dur, amp, sr=SR, armonicos=6):
    f = 440 * 2 ** ((midi - 69) / 12)
    i, n = int(t0 * sr), int(dur * sr)
    t = np.arange(n) / sr
    s = sum(0.6 ** (h - 1) * np.sin(2 * np.pi * f * h * t) for h in range(1, armonicos + 1) if f * h < sr / 2)
    y[i : i + n] += amp * s * np.exp(-t * 2.5) * np.minimum(1, t * 200)


def _bombo(y, t0, sr=SR):
    i, n = int(t0 * sr), int(0.2 * sr)
    t = np.arange(n) / sr
    y[i : i + n] += 0.9 * np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 15)


def _hihat(y, t0, rng, sr=SR):
    i, n = int(t0 * sr), int(0.05 * sr)
    ruido = np.diff(rng.standard_normal(n + 1)) * np.exp(-np.arange(n) / sr * 80)
    y[i : i + n] += 0.25 * ruido


def _cancion_sintetica(bpm=100, compases=6, sr=44100):
    pulso = 60 / bpm
    y = np.zeros(int(sr * pulso * 4 * compases) + sr)
    rng = np.random.default_rng(0)
    acordes = [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]]
    bajos = [36, 33, 29, 31]
    for c in range(compases):
        t0 = c * 4 * pulso
        for k in range(4):
            for m in acordes[c % 4]:
                _tono(y, m, t0 + k * pulso, pulso * 0.9, 0.15, sr)
        for k in (0, 2):
            _tono(y, bajos[c % 4], t0 + k * pulso, pulso * 1.9, 0.4, sr, armonicos=3)
            _bombo(y, t0 + k * pulso, sr)
        for k in range(8):
            _hihat(y, t0 + k * pulso / 2, rng, sr)
    return (y / (np.abs(y).max() * 1.1)).astype(np.float32), bajos


def _notas_por_canal(ruta):
    mid = mido.MidiFile(str(ruta))
    salida = defaultdict(list)
    for pista in mid.tracks:
        t = 0
        for msg in pista:
            t += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                salida[msg.channel].append((t / mid.ticks_per_beat, msg.note))
    return mid, salida


# ----------------------------------------------------------------- escritura MIDI
def test_midi_formato0_con_reset_gm_xg_y_voces(tmp_path):
    partes = [
        Parte("Piano", 1, 0, [Nota(0.0, 0.5, 60, 100), Nota(0.5, 1.0, 64, 90)]),
        Parte("Bateria", 9, 0, [Nota(0.0, 0.1, BOMBO, 110)], bateria=True),
    ]
    ruta = escribir_midi(partes, tmp_path / "x.mid", bpm=120, compas_entrada=True)
    mid = mido.MidiFile(str(ruta))
    assert mid.type == 0 and len(mid.tracks) == 1
    msgs = list(mid.tracks[0])
    sysex = [list(m.data) for m in msgs if m.type == "sysex"]
    assert sysex[:2] == [GM_ON, XG_ON]
    tempos = [m for m in msgs if m.type == "set_tempo"]
    assert mido.tempo2bpm(tempos[0].tempo) == pytest.approx(120)
    bancos = {(m.channel, m.value) for m in msgs if m.type == "control_change" and m.control == 0}
    assert (9, 127) in bancos and (1, 0) in bancos  # batería XG en banco 127
    programas = {(m.channel, m.program) for m in msgs if m.type == "program_change"}
    assert programas == {(1, 0), (9, 0)}

    _, notas = _notas_por_canal(ruta)
    # Compás de entrada (4 pulsos) y luego las notas a 120 BPM: 0.5 s = 1 pulso.
    assert notas[1] == [(4.0, 60), (5.0, 64)]
    assert notas[9] == [(4.0, BOMBO)]


def test_midi_formato1_una_pista_por_instrumento(tmp_path):
    partes = [Parte("A", 0, 73, [Nota(0, 1, 70, 80)]), Parte("B", 2, 33, [Nota(0, 1, 40, 80)])]
    mid = mido.MidiFile(str(escribir_midi(partes, tmp_path / "y.mid", formato=1)))
    assert mid.type == 1 and len(mid.tracks) == 3


def test_cuantizacion_y_solapamientos(tmp_path):
    notas = [
        Nota(0.02, 0.40, 60, 100),  # inicio ligeramente desfasado
        Nota(0.30, 0.90, 60, 90),  # misma nota antes de que termine la anterior
    ]
    ruta = escribir_midi(
        [Parte("P", 0, 0, notas)], tmp_path / "q.mid", bpm=60, cuantizar=4, compas_entrada=False
    )
    mid = mido.MidiFile(str(ruta))
    t, activas, inicios = 0, set(), []
    for msg in mid.tracks[0]:
        t += msg.time
        if msg.type == "note_on" and msg.velocity:
            assert msg.note not in activas, "nota tocada dos veces sin soltarse"
            activas.add(msg.note)
            inicios.append(t)
        elif msg.type in ("note_off", "note_on"):
            activas.discard(msg.note)
    assert all(i % (PPQ // 4) == 0 for i in inicios)
    assert inicios == [0, PPQ // 4]


def test_nombre_archivo_seguro():
    assert nombre_archivo_seguro("Alabaré a mi Señor (en vivo)!") == "Alabare_a_mi_Senor_en_vivo"
    assert nombre_archivo_seguro("***") == "cancion"


# ----------------------------------------------------------------- transcripción
def test_acordes_polifonicos():
    y = np.zeros(SR * 6)
    acordes = [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]]
    for k, acorde in enumerate(acordes):
        for m in acorde:
            _tono(y, m, k * 1.2, 1.1, 0.2)
    notas = transcribir_polifonico_propio(y.astype(np.float32), SR)
    for k, acorde in enumerate(acordes):
        sonando = {n.tono for n in notas if abs(n.inicio - k * 1.2) < 0.08}
        assert sonando == set(acorde), (k, sonando)


def test_bajo_monofonico():
    y = np.zeros(SR * 5)
    linea = [36, 40, 43, 41]
    for k, m in enumerate(linea):
        _tono(y, m, k * 1.0, 0.9, 0.5, armonicos=3)
    notas = transcribir_monofonico(y.astype(np.float32), SR, (28, 62))
    assert [n.tono for n in notas] == linea
    for k, n in enumerate(notas):
        assert n.inicio == pytest.approx(k * 1.0, abs=0.06)


def test_bateria_bombo_en_su_lugar():
    y = np.zeros(SR * 3)
    rng = np.random.default_rng(1)
    for k in range(4):
        _bombo(y, k * 0.6)
        _hihat(y, k * 0.6 + 0.3, rng)
    notas = transcribir_bateria(y.astype(np.float32), SR, mezcla=y.astype(np.float32))
    bombos = [n.inicio for n in notas if n.tono == BOMBO]
    assert len(bombos) == 4
    assert np.allclose(bombos, [0, 0.6, 1.2, 1.8], atol=0.03)


def test_tempo_y_fase():
    fps = 100.0
    env = np.zeros(2000)
    env[(np.arange(0.25, 19.5, 0.5) * fps).astype(int)] = 1.0  # 120 BPM, primer pulso en 0.25 s
    bpm, fase = afinar_tempo_y_fase(env, fps, 118.0)
    assert bpm == pytest.approx(120, abs=0.3)
    assert fase == pytest.approx(0.25, abs=0.02)


# ----------------------------------------------------------------- proceso completo
def test_conversion_completa_modo_basico(tmp_path):
    import soundfile as sf

    y, bajos = _cancion_sintetica()
    wav = tmp_path / "Canción de prueba.wav"
    sf.write(str(wav), y, 44100)
    res = convertir(wav, usar_ia=False, log=lambda _m: None)

    assert res.archivo.name == "Cancion_de_prueba.mid"
    assert res.bpm == pytest.approx(100, abs=1)
    mid, notas = _notas_por_canal(res.archivo)
    assert mid.type == 0
    # Bajo en el canal 3, con las notas reales de la línea (como mucho un error de octava).
    assert {n % 12 for _, n in notas[2]} <= {b % 12 for b in bajos}
    assert {b % 12 for b in bajos} <= {n % 12 for _, n in notas[2]}
    # Batería en el canal 10, con bombos alineados al pulso (después del compás de entrada).
    bombos = [t for t, n in notas[9] if n == BOMBO]
    assert len(bombos) >= 10
    desvios = [abs(t - round(t)) for t in bombos]
    assert np.median(desvios) < 0.05 and max(desvios) < 0.2
    # Acompañamiento en el canal 2 y parecido armónico alto (señal sintética limpia).
    assert len(notas[1]) > 20
    assert res.parecido > 0.7


def test_separacion_demucs_en_proceso(tmp_path, monkeypatch):
    """Simula el modelo de Demucs (sin descargarlo) y verifica que las pistas
    salen con su nombre, en mono y a la frecuencia de trabajo."""
    import sys
    import types

    import soundfile as sf

    torch = pytest.importorskip("torch")  # Demucs es opcional (el .exe usa el separador MDX)
    from psr_midi import separation

    y, _ = _cancion_sintetica(compases=1)
    wav = tmp_path / "x.wav"
    sf.write(str(wav), y, 44100)

    class RedFalsa:
        samplerate = 44100
        sources = list(separation.STEMS_DEMUCS)

        def eval(self):
            return self

    def apply_falso(red, mezcla, **_kw):
        return mezcla[:, None].repeat(1, len(red.sources), 1, 1)

    monkeypatch.setitem(sys.modules, "demucs.pretrained", types.SimpleNamespace(get_model=lambda _n: RedFalsa()))
    monkeypatch.setitem(sys.modules, "demucs.apply", types.SimpleNamespace(apply_model=apply_falso))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    sep = separation.separar_demucs(wav, log=lambda _m: None)
    assert set(sep.pistas) == set(separation.STEMS_DEMUCS)
    assert sep.motor == "demucs:htdemucs"
    largo = int(len(y) * SR / 44100)
    for pista in sep.pistas.values():
        assert pista.ndim == 1 and abs(len(pista) - largo) < 50
    # La pista reconstruida debe parecerse a la mezcla (el modelo falso la copia).
    assert np.corrcoef(sep.pistas["drums"][:largo - 50], sep.mezcla[:largo - 50])[0, 1] > 0.99


def test_linea_monofonica_aguda_y_grave():
    notas = [Nota(0.0, 1.0, 60, 90), Nota(0.0, 1.0, 64, 90), Nota(0.5, 1.5, 67, 90), Nota(1.6, 2.0, 62, 90)]
    aguda = linea_monofonica(notas, aguda=True)
    assert [(n.tono, round(n.inicio, 2), round(n.fin, 2)) for n in aguda] == [(64, 0.0, 0.5), (67, 0.5, 1.5), (62, 1.6, 2.0)]
    grave = linea_monofonica(notas, aguda=False)
    assert [n.tono for n in grave][:2] == [60, 67]
    # Nunca hay dos notas sonando a la vez.
    for linea in (aguda, grave):
        assert all(a.fin <= b.inicio + 1e-9 for a, b in zip(linea, linea[1:]))


def test_partes_desde_pistas_separadas():
    """Con la voz separada, cada parte sale de su pista: voz -> melodía; del
    instrumental: graves -> bajo, medios -> acordes."""
    from psr_midi.converter import transcribir_partes
    from psr_midi.separation import Separacion

    n = SR * 5
    voz, bajo, otros = np.zeros(n), np.zeros(n), np.zeros(n)
    melodia = [72, 74, 76, 77]
    for k, m in enumerate(melodia):
        _tono(voz, m, k * 1.0, 0.9, 0.4, armonicos=4)
        _tono(bajo, 36 + (k % 2) * 7, k * 1.0, 0.9, 0.5, armonicos=3)
        for c in (60, 64, 67):
            _tono(otros, c, k * 1.0, 0.9, 0.15)
    pistas = {"vocals": voz, "armonica": bajo + otros, "drums": np.zeros(n)}
    pistas = {k: v.astype(np.float32) for k, v in pistas.items()}
    sep = Separacion(sr=SR, mezcla=(voz + bajo + otros).astype(np.float32), pistas=pistas, motor="mdx")
    partes = transcribir_partes(sep, log=lambda _m: None)
    assert [x.tono for x in partes["melodia"]] == melodia
    assert {x.tono % 12 for x in partes["bajo"]} <= {0, 7}  # do y sol (se admite error de octava)
    assert {60, 64, 67} <= {x.tono for x in partes["acompanamiento"]}
    assert not {x.tono for x in partes["acompanamiento"]} & set(melodia)


def test_mdx_stft_reconstruye_la_senal():
    """Con un modelo que devuelve su entrada, la separación MDX debe reconstruir
    la mezcla (comprueba la STFT/ISTFT y el troceado)."""
    import types

    from psr_midi import mdx

    sep = mdx.SeparadorMDX.__new__(mdx.SeparadorMDX)
    sep.p = mdx.MODELOS["voz"]
    sep.ventana = np.hanning(sep.p.n_fft + 1)[:-1].astype(np.float32)
    sep.trozo = sep.p.hop * (sep.p.dim_t - 1)
    entrada = types.SimpleNamespace(name="input")
    sep.sesion = types.SimpleNamespace(get_inputs=lambda: [entrada], run=lambda _o, d: [d["input"]])

    sr = 44100
    t = np.arange(int(sr * 8)) / sr
    x = np.stack([np.sin(2 * np.pi * 440 * t), 0.5 * np.sin(2 * np.pi * 1000 * t)]).astype(np.float32)
    y = sep.separar(x) / sep.p.compensar
    assert y.shape == x.shape
    assert np.max(np.abs(y[:, 2000:-2000] - x[:, 2000:-2000])) < 1e-3


def test_quitar_armonicos_de_la_voz():
    from psr_midi.converter import quitar_armonicos

    notas = [Nota(0, 1, 60, 120), Nota(0.1, 0.8, 72, 70), Nota(1, 2, 62, 110)]
    assert [n.tono for n in quitar_armonicos(notas)] == [60, 62]
