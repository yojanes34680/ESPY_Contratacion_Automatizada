# ESPY - Sistema de Contratación Automatizada para Empresas de Servicios Públicos (ESP)

Sistema integral para la administración, estructuración, redacción automatizada con IA y sincronización del ciclo contractual en Empresas de Servicios Públicos Domiciliarios en Colombia.

---

## 1. Fundamento Normativo
El sistema está diseñado para cumplir con el régimen jurídico aplicable a las **Empresas de Servicios Públicos (ESP)**:
* **Ley 142 de 1994 (Art. 31 y concordantes):** Régimen contractual de derecho privado (Código de Comercio y Código Civil).
* **Constitución Política de Colombia (Art. 209 y 267):** Sujeción estricta a los principios de la función administrativa y la gestión fiscal (igualdad, moralidad, eficacia, economía, celeridad, imparcialidad y publicidad).
* **Manual Interno de Contratación (MIC):** Parametrización de modalidades de selección (Contratación Directa, Invitación Privada, Invitación Pública y Mínima Cuantía).

---

## 2. Estructura del Proyecto

```
ESPY_Contratacion_Automatizada/
├── backend/
│   ├── app/
│   │   ├── config.py             # Configuración y resolución de rutas
│   │   ├── database.py           # Conexión SQLAlchemy 2.0 y sesiones
│   │   ├── main.py               # Aplicación FastAPI y middlewares
│   │   ├── models/               # Modelos relacionales ORM (Contratista, Contrato, Documento, Auditoria)
│   │   ├── schemas/              # Validación y serialización Pydantic v2
│   │   ├── routers/              # Endpoints API (/contractors, /contracts, /documents)
│   │   ├── services/             # Lógica de negocio, agentes LLM y parsers
│   │   └── utils/                # Conversor de moneda legal a letras y logger
│   ├── master_excel/             # Plantilla y matriz maestra de contratación
│   ├── storage/                  # Almacenamiento local (uploads/ y generated/)
│   ├── templates/                # Plantillas Word (.docx)
│   └── requirements.txt          # Dependencias Python
├── frontend/                     # Interfaz de Usuario SPA
├── .env.example                  # Plantilla de variables de entorno
├── README.md                     # Documentación general
├── run_server.py                 # Script de inicio rápido del servidor
└── validate_all.py               # Suite de pruebas automatizadas
```

---

## 3. Instalación y Ejecución

### Requisitos Previos
* Python 3.10 o superior (validado en Python 3.14).

### Iniciar el Servidor Backend
```bash
python run_server.py
```
* **API y Servidor Local:** `http://127.0.0.1:8000`
* **Documentación Interactiva Swagger:** `http://127.0.0.1:8000/docs`
* **Especificación ReDoc:** `http://127.0.0.1:8000/redoc`

### Ejecutar Pruebas Automatizadas
```bash
python validate_all.py
```

---

## 4. Endpoints Disponibles (Fase 1)

### Contratistas (`/api/contractors`)
* `POST /api/contractors`: Registrar nuevo contratista (Persona Natural o Jurídica).
* `GET /api/contractors`: Listar contratistas con filtros por búsqueda de texto y paginación.
* `GET /api/contractors/{id}`: Detalle de un contratista.
* `PUT /api/contractors/{id}`: Actualizar datos de un contratista.
* `PATCH /api/contractors/{id}/deactivate`: Desactivar contratista (marca `activo = False`), preservando su histórico contractual sin permitir borrado físico si tiene contratos.
* `DELETE /api/contractors/{id}`: Eliminar contratista (permitido únicamente si no tiene contratos registrados).

### Contratos (`/api/contracts`)
* `POST /api/contracts`: Crear nuevo contrato. Calcula automáticamente el valor en letras en pesos colombianos (`M/CTE`) si no es provisto.
* `GET /api/contracts`: Listar contratos con filtros por tipología, estado, vigencia, contratista y parámetro `ocultar_anulados`.
* `GET /api/contracts/{id}`: Detalle del contrato con datos del contratista, documentos y trazabilidad.
* `PUT /api/contracts/{id}`: Actualizar campos del contrato.
* `PATCH /api/contracts/{id}/status`: Transición formal basada en el grafo de ciclo de vida (`BORRADOR` -> `EN_REVISION` -> `APROBADO` -> `EN_EJECUCION` -> `TERMINADO` -> `LIQUIDADO` / `SUSPENDIDO`). Transiciones excepcionales fuera del grafo solo permitidas al rol `ADMIN` con observación obligatoria. Limpia automáticamente overrides de fecha al volver a `EN_EJECUCION`.
* `DELETE /api/contracts/{id}`: Anulación / Eliminación controlada. Requiere justificación con motivo $\ge 15$ caracteres. Si el contrato está en ejecución, terminado o con pagos/adiciones, pasa de forma irreversible a estado `ANULADO` con autor y fecha, actualizándose en la Matriz Excel. Solo se permite borrado físico en contratos `BORRADOR` sin pagos ni adiciones ejecutado por `ADMIN`, preservando la auditoría de forma desvinculada.
* `GET /api/contracts/catalogs/typologies`: Catálogo normativo de tipologías para ESP (Servicios, Obra, Suministro, Consultoría, Interventoría).
* `GET /api/contracts/catalogs/modalities`: Catálogo de modalidades de selección.

### Plantillas Word (.docx) (`/api/templates`)
* `GET /api/templates/available`: Catálogo de plantillas oficiales para Estudio Previo, Minuta del Contrato y Acta de Inicio.
* `POST /api/templates/generate/{contract_id}/{template_type}`: Ensambla el documento Word reemplazando los placeholders sin alterar formatos, tablas ni membretes.
* `GET /api/templates/download/{contract_id}/{template_type}`: Descarga directa del archivo `.docx` generado.

### Interfaz de Usuario SPA (`/app/` y `/`)
* **Acceso Directo:** Navegar a `http://127.0.0.1:8000/app/` o `http://127.0.0.1:8000/`.
* **Dashboard:** Visualización de KPIs (Total Contratos, Presupuesto Comprometido en COP, Contratos Activos), distribución por tipología y tabla de contratos recientes.
* **Directorio de Contratos:** Filtros en tiempo real por búsqueda de texto, tipología y estado, con modal de detalle completo y cambio de estados contractuales con auditoría.
* **Asistente de Contratación IA (Wizard):** Flujo de 4 pasos para carga de documentos, extracción con IA, redacción especializada por agentes y ensamblaje de documentos.
* **Matriz de Excel Maestro:** Previsualización en vivo de la matriz, botón de sincronización masiva y descarga de `Matriz_Contratacion_Maestra_ESP.xlsx`.
* **Configuración:** Registro de `GEMINI_API_KEY`, comprobación de directorios y resumen del marco legal.

---

## 6. Estado del Proyecto: 100% Completado y Operacional
El sistema cuenta con una suite integral de pruebas automatizadas aisladas de la base de datos de producción mediante base temporal SQLite y monkeypatch controlado. Para ejecutar la suite completa de pruebas:
```bash
python -m pytest -q
```
Actualmente cuenta con **30 pruebas integrales** (15 casos de regresión en `test_regression_suite.py`, 6 pruebas de flujo y CRUD en `tests/test_validate_all.py`, y 9 pruebas especializadas de CDP en `tests/test_cdp_*.py`), todas pasando al 100%.

Para arrancar el servidor en desarrollo o producción:
```bash
python run_server.py
```

---

## 7. Regeneración de Índices UNSPSC (.pickle)
Los archivos de catálogo e índice BM25 (`codigos_unspsc_cache.pickle` y `unspsc_bm25_index.pickle`) ubicados en `backend/app/resources/` no se versionan en Git. Para regenerarlos a partir de la fuente oficial o reconstruir el índice BM25, ejecute:

```bash
python tools/build_unspsc_index.py
```
Este script reconstruye el índice y actualiza los artefactos serializados necesarios para la clasificación inteligente de códigos UNSPSC.

