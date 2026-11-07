# Lector Ilustrado

Programa para PC que convierte un PDF de literatura en un **libro ilustrado y narrado**:

1. Lee el texto del PDF y reconstruye los párrafos.
2. **Claude** estudia la obra y arma una *ficha de producción*: época, lugar,
   contexto histórico, estilo visual y la descripción física fija de cada
   personaje, para que se vean iguales en todas las imágenes.
3. Divide el texto en **escenas** y reparte cada frase entre el **narrador** y
   los **personajes** que hablan.
4. Genera una **imagen por escena** respetando la época (OpenAI).
5. Graba cada frase con una **voz distinta por personaje** y con la emoción
   indicada (OpenAI).
6. Abre un **lector web interactivo**: imagen grande, texto resaltado mientras
   suena la voz y cambio automático de escena.

Este programa es independiente del sistema de contratación de la ESPY: vive en
su propia carpeta y no toca nada de ese sistema.

## Cómo iniciarlo en Windows

1. Instale **Python 3.10 o superior** desde <https://www.python.org/downloads/>
   y marque la casilla *"Add Python to PATH"* durante la instalación.
2. Haga doble clic en **`INICIAR_LECTOR.bat`**. La primera vez tarda unos
   minutos porque instala lo necesario.
3. Se abre el navegador en `http://127.0.0.1:8765`. No cierre la ventana negra
   mientras use el lector.

En otro sistema operativo:

```bash
cd lector_ilustrado
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m lector.servidor
```

## Claves de acceso

En el botón **Configuración** del programa se pegan dos claves. Se guardan solo
en este computador, en `lector_ilustrado/.env`, y nunca se suben a git.

| Clave | Para qué | Dónde se obtiene |
|---|---|---|
| Anthropic (Claude) | Analizar la obra, escenas y voces | <https://console.anthropic.com> → API Keys |
| OpenAI | Imágenes y voces naturales | <https://platform.openai.com> → API keys |

Ambos servicios son de pago por uso: hay que cargar un saldo en cada cuenta.
Consulte los precios vigentes en sus páginas. Para controlar el gasto:

- En **Nueva obra**, indique un rango de páginas y un **máximo de escenas**
  (por defecto 12).
- Cada escena genera una sola imagen; la voz se cobra según la cantidad de texto.
- Lo ya generado queda guardado y no se vuelve a cobrar al releer.

## Modo gratuito

Sin claves también se puede probar. Elija **Básico, sin IA**, **Láminas
provisionales** y **Voces del computador**. El texto se divide por párrafos,
los diálogos se detectan por las rayas (—), las imágenes son láminas de color y
la lectura la hace la voz instalada en Windows.

Las opciones se pueden mezclar, por ejemplo análisis con Claude e imágenes con
IA, pero voces del computador para ahorrar.

## Uso del lector

- **Espacio**: leer / pausar. **← →**: escena anterior / siguiente.
- Clic sobre cualquier frase para leer desde ahí.
- **Sobre la obra** muestra la ficha: época, lugar, estilo y personajes.
- **Otra imagen** permite corregir la descripción de la escena y volver a
  pintarla.

## Limitaciones conocidas

- PDF escaneados (fotos de páginas) todavía no se leen: el PDF debe tener texto
  seleccionable.
- La atribución de diálogos acierta en la gran mayoría de los casos, pero puede
  fallar en conversaciones largas sin incisos ("dijo Juan").
- La apariencia de los personajes se mantiene por descripción; puede variar un
  poco entre imágenes.
- Respete los derechos de autor: las obras de dominio público no tienen
  problema. Con obras protegidas, use el programa solo para lectura personal.

## Estructura

```
lector_ilustrado/
├── INICIAR_LECTOR.bat     arranque con doble clic (Windows)
├── lector/
│   ├── extraer.py         PDF/TXT → párrafos
│   ├── analizar.py        ficha de la obra, escenas y voces (Claude o básico)
│   ├── medios.py          imágenes y voces (OpenAI o gratuito)
│   ├── proyecto.py        flujo completo y almacenamiento en datos/<id>/
│   └── servidor.py        servidor web local
├── web/                   lector interactivo (HTML, CSS, JS)
└── tests/                 pruebas automáticas (python -m pytest)
```

Modelos configurables en `.env` (ver `.env.example`).
