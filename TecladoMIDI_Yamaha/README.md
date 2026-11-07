# Canción a MIDI para Yamaha PSR-S950

Programa para computadora que toma una canción en **MP3, MP4, M4A, WAV, FLAC, OGG**
(o cualquier video con audio) y crea una **secuencia MIDI (.mid)** que el teclado
**Yamaha PSR-S950** reproduce con sus propios sonidos: piano, bajo, batería,
guitarra, cuerdas y la melodía de la voz, cada uno en su propio canal.

El archivo no es una grabación: son las **notas** de cada instrumento. Por eso en el
teclado se puede cambiar el tempo, transportar el tono, silenciar o cambiar
el sonido de cada instrumento, y ver la partitura en pantalla.

---

## ¿Qué tan fiel queda la canción?

Ningún programa (ni comercial ni gratuito) produce todavía una **copia exacta**
de una canción grabada. El resultado depende de la grabación:

| Funciona muy bien | Funciona regular |
|---|---|
| Alabanzas con pocos instrumentos y sonido limpio | Mezclas muy densas (orquestas, coros grandes) |
| Piano y voz, guitarra y voz | Grabaciones en vivo con mucho eco o ruido |
| Bajo y batería bien marcados | Sintetizadores con efectos y "pads" largos |

Lo normal es obtener una **base muy buena** (acordes, bajo, ritmo y melodía
correctos en la mayor parte de la canción) que luego se puede pulir en el
teclado (Song Creator) o en un editor MIDI gratuito como **MuseScore** o
**Anvil Studio**.

La calidad sube mucho al instalar los motores de inteligencia artificial
(paso 3 de la instalación):

- **Demucs** (Meta): separa la canción en voz, batería, bajo, piano, guitarra y otros.
- **Basic Pitch** (Spotify): reconoce acordes y notas simultáneas con mayor precisión.

Sin ellos el programa sigue funcionando en un **modo básico** (separa solo
batería, bajo y acordes, sin la melodía de la voz).

---

## Cómo se organizan los instrumentos en el teclado

| Canal | Instrumento | Botón del PSR-S950 |
|---|---|---|
| 1 | Melodía de la voz (sonido elegible: flauta, coro, violín...) | **[TRACK 1]** |
| 2 | Piano / acordes | **[TRACK 2]** |
| 3 | Bajo | [EXTRA TRACKS] |
| 4 | Guitarra | [EXTRA TRACKS] |
| 5 | Cuerdas / teclados | [EXTRA TRACKS] |
| 10 | Batería | [EXTRA TRACKS] |

Así, para **cantar con la pista**, se apaga **[TRACK 1]** y la melodía deja de
sonar mientras el resto del acompañamiento sigue. Para tocar el piano en vivo,
se apaga **[TRACK 2]**.

El archivo incluye al inicio los mensajes *GM System On* y *XG System On*, de
modo que el teclado siempre carga los sonidos correctos, y un compás de silencio
para que todo quede listo antes de empezar.

---

## Instalación en Windows

1. Instale **Python 3.11** desde <https://www.python.org/downloads/>
   (marque la casilla **"Add python.exe to PATH"**).
   Se recomienda 3.11 porque Basic Pitch aún no funciona en versiones más nuevas.
2. Copie la carpeta `TecladoMIDI_Yamaha` a su computadora.
3. Haga doble clic en **`INSTALAR.bat`**. Instala ffmpeg (para leer MP3/MP4), las
   librerías y los motores de IA. Descarga cerca de 2 GB, así que puede tardar.
4. Abra el programa con **`INICIAR_CONVERTIDOR.bat`**.

> La primera vez que se use Demucs descargará su modelo (~80 MB) de Internet.

## Uso

1. Pulse **Buscar...** y elija la canción (MP3, MP4...).
2. Elija las opciones:
   - **Ajuste rítmico**: *Tiempo exacto* conserva el "sentimiento" original;
     *Semicorcheas* alinea las notas a la cuadrícula (queda más limpio en la partitura).
   - **Tempo**: déjelo vacío para detectarlo solo; escríbalo si ya lo conoce.
   - **Sonido de la melodía**: con qué voz del teclado sonará la línea del cantante.
   - **Instrumentos a incluir**: quite los que no quiera en la secuencia.
   - **Formato SMF**: deje **0** (el más compatible con los teclados Yamaha).
3. Pulse **Convertir a MIDI**. Con IA y sin tarjeta gráfica, una canción de
   4 minutos puede tardar entre 5 y 15 minutos.

### Por consola (opcional)

```bat
python -m psr_midi.cli "Mi cancion.mp3"
python -m psr_midi.cli video.mp4 -o Alabanza.mid --cuantizar 4 --bpm 72
python -m psr_midi.cli cancion.mp3 --sin-melodia --gpu
```

## Cómo reproducirla en el PSR-S950

1. Copie el archivo `.mid` a una memoria USB (formateada en FAT32).
2. Conecte la memoria en el puerto **USB TO DEVICE** del teclado.
3. Pulse **[SONG SELECT]** (botón *SONG*), vaya a la pestaña **USB** y elija la canción.
4. Pulse **[PLAY/PAUSE]** en la sección SONG.
5. Use **[TRACK 1]**, **[TRACK 2]** y **[EXTRA TRACKS]** para silenciar partes;
   **[TEMPO −/+]** para cambiar la velocidad y **[TRANSPOSE]** para el tono.
6. Si quiere corregir notas o cambiar sonidos y guardarlos en el teclado,
   use **[DIGITAL RECORDING] → Song Creator** y guarde de nuevo en USB o *User*.

---

## Estructura del código

```
TecladoMIDI_Yamaha/
├── INSTALAR.bat / INICIAR_CONVERTIDOR.bat   Lanzadores para Windows
├── requirements.txt / requirements-ia.txt   Dependencias (núcleo / IA opcional)
├── psr_midi/
│   ├── audio_io.py       Lectura de MP3/MP4/WAV con ffmpeg
│   ├── separation.py     Separación de instrumentos (Demucs o modo básico)
│   ├── transcription.py  Audio → notas (Basic Pitch, motor CQT propio, pYIN)
│   ├── drums.py          Batería → bombo, redoblante, hi-hat, platillo (GM)
│   ├── yamaha.py         Escritura del .mid (GM/XG, canales, voces)
│   ├── converter.py      Proceso completo + detección de tempo y compás
│   ├── cli.py / gui.py   Consola y ventana
└── tests/                Pruebas con audio sintético
```

Ejecutar las pruebas: `cd TecladoMIDI_Yamaha && python -m pytest`.
