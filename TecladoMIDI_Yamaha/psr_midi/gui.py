"""Ventana sencilla para convertir canciones sin usar la consola."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .converter import VOCES_GM, configuracion_por_defecto, convertir
from .separation import demucs_disponible
from .transcription import basic_pitch_disponible
from .yamaha import nombre_archivo_seguro

TIPOS = [
    ("Audio y video", "*.mp3 *.mp4 *.m4a *.wav *.flac *.ogg *.aac *.wma *.mkv *.mov *.avi *.webm"),
    ("Todos", "*.*"),
]
CUANTIZACION = {"Tiempo exacto (sin ajustar)": None, "Corcheas": 2, "Semicorcheas": 4, "Fusas": 8}
NOMBRES_PISTA = {
    "vocals": "Melodía de la voz (canal 1)",
    "piano": "Piano / acordes (canal 2)",
    "bass": "Bajo (canal 3)",
    "guitar": "Guitarra (canal 4)",
    "other": "Cuerdas / teclados (canal 5)",
    "drums": "Batería (canal 10)",
}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Canción a MIDI para Yamaha PSR-S950")
        self.geometry("760x620")
        self.minsize(640, 520)
        # Mensajes de texto o funciones a ejecutar en el hilo de la ventana (tkinter no es multihilo).
        self.cola: queue.Queue = queue.Queue()
        self.config_inst = configuracion_por_defecto()

        self.var_entrada = tk.StringVar()
        self.var_salida = tk.StringVar()
        self.var_ia = tk.BooleanVar(value=True)
        self.var_cuant = tk.StringVar(value="Tiempo exacto (sin ajustar)")
        self.var_formato = tk.StringVar(value="0")
        self.var_bpm = tk.StringVar()
        self.var_voz_melodia = tk.StringVar(value="Flauta")
        self.var_pistas = {k: tk.BooleanVar(value=True) for k in NOMBRES_PISTA}

        self._construir()
        self.after(150, self._leer_cola)

    # ------------------------------------------------------------------ UI
    def _construir(self) -> None:
        pad = {"padx": 8, "pady": 4}
        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True, padx=10, pady=10)
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text="Canción (MP3, MP4, WAV...):").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(marco, textvariable=self.var_entrada).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(marco, text="Buscar...", command=self._elegir_entrada).grid(row=0, column=2, **pad)

        ttk.Label(marco, text="Guardar MIDI como:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(marco, textvariable=self.var_salida).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(marco, text="Cambiar...", command=self._elegir_salida).grid(row=1, column=2, **pad)

        opciones = ttk.LabelFrame(marco, text="Opciones")
        opciones.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        estado_ia = []
        estado_ia.append("Demucs ✔" if demucs_disponible() else "Demucs ✘")
        estado_ia.append("Basic Pitch ✔" if basic_pitch_disponible() else "Basic Pitch ✘")
        ttk.Checkbutton(
            opciones, text=f"Usar inteligencia artificial ({', '.join(estado_ia)})", variable=self.var_ia
        ).grid(row=0, column=0, columnspan=4, sticky="w", **pad)
        ttk.Label(opciones, text="Ajuste rítmico:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(
            opciones, textvariable=self.var_cuant, values=list(CUANTIZACION), state="readonly", width=26
        ).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(opciones, text="Tempo (vacío = automático):").grid(row=1, column=2, sticky="w", **pad)
        ttk.Entry(opciones, textvariable=self.var_bpm, width=8).grid(row=1, column=3, sticky="w", **pad)
        ttk.Label(opciones, text="Sonido de la melodía:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(
            opciones, textvariable=self.var_voz_melodia, values=list(VOCES_GM), state="readonly", width=26
        ).grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(opciones, text="Formato SMF:").grid(row=2, column=2, sticky="w", **pad)
        ttk.Combobox(
            opciones, textvariable=self.var_formato, values=["0", "1"], state="readonly", width=6
        ).grid(row=2, column=3, sticky="w", **pad)

        pistas = ttk.LabelFrame(marco, text="Instrumentos a incluir")
        pistas.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        for i, (clave, texto) in enumerate(NOMBRES_PISTA.items()):
            ttk.Checkbutton(pistas, text=texto, variable=self.var_pistas[clave]).grid(
                row=i // 2, column=i % 2, sticky="w", **pad
            )

        self.boton = ttk.Button(marco, text="Convertir a MIDI", command=self._convertir)
        self.boton.grid(row=4, column=0, columnspan=3, pady=8)
        self.barra = ttk.Progressbar(marco, mode="indeterminate")
        self.barra.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)

        self.log = tk.Text(marco, height=12, wrap="word", state="disabled")
        self.log.grid(row=6, column=0, columnspan=3, sticky="nsew", **pad)
        marco.rowconfigure(6, weight=1)

    def _elegir_entrada(self) -> None:
        ruta = filedialog.askopenfilename(title="Elegir canción", filetypes=TIPOS)
        if ruta:
            self.var_entrada.set(ruta)
            p = Path(ruta)
            self.var_salida.set(str(p.with_name(nombre_archivo_seguro(p.stem) + ".mid")))

    def _elegir_salida(self) -> None:
        ruta = filedialog.asksaveasfilename(
            title="Guardar MIDI", defaultextension=".mid", filetypes=[("Archivo MIDI", "*.mid")]
        )
        if ruta:
            self.var_salida.set(ruta)

    def _escribir(self, texto: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _leer_cola(self) -> None:
        try:
            while True:
                item = self.cola.get_nowait()
                if callable(item):
                    item()
                else:
                    self._escribir(str(item))
        except queue.Empty:
            pass
        self.after(150, self._leer_cola)

    # ------------------------------------------------------------ proceso
    def _convertir(self) -> None:
        entrada = self.var_entrada.get().strip()
        if not entrada or not Path(entrada).exists():
            messagebox.showwarning("Falta la canción", "Elija primero un archivo de audio o video.")
            return
        bpm = None
        if self.var_bpm.get().strip():
            try:
                bpm = float(self.var_bpm.get().replace(",", "."))
            except ValueError:
                messagebox.showwarning("Tempo inválido", "Escriba el tempo como número, por ejemplo 72.")
                return

        config = configuracion_por_defecto()
        for clave, var in self.var_pistas.items():
            config[clave].activo = var.get()
        config["vocals"].programa = VOCES_GM[self.var_voz_melodia.get()]

        kwargs = dict(
            entrada=entrada,
            salida=self.var_salida.get().strip() or None,
            usar_ia=self.var_ia.get(),
            cuantizar=CUANTIZACION[self.var_cuant.get()],
            formato=int(self.var_formato.get()),
            config=config,
            bpm_manual=bpm,
            log=self.cola.put,
        )
        self.boton.configure(state="disabled")
        self.barra.start(12)
        threading.Thread(target=self._trabajo, kwargs=kwargs, daemon=True).start()

    def _trabajo(self, **kwargs) -> None:
        try:
            res = convertir(**kwargs)
            resumen = "\n".join(f"  {k}: {v} notas" for k, v in res.notas_por_parte.items())
            self.cola.put(f"\n✔ Archivo listo ({res.bpm:.1f} BPM):\n{res.archivo}\n{resumen}")
            self.cola.put(lambda: messagebox.showinfo(
                "Conversión terminada",
                f"Se creó:\n{res.archivo}\n\nCópielo a una memoria USB y ábralo en el teclado con el botón SONG.",
            ))
        except Exception as exc:  # noqa: BLE001
            mensaje = str(exc)
            self.cola.put(f"✘ Error: {mensaje}")
            self.cola.put(lambda: messagebox.showerror("Error", mensaje))
        finally:
            self.cola.put(self._terminar)

    def _terminar(self) -> None:
        self.barra.stop()
        self.boton.configure(state="normal")


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
