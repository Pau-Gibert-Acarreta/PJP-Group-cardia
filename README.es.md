# Cardia

> [English version](README.md)

Prototipo de una consulta de Atención Primaria para explorar el riesgo cardiovascular de los 4.434 pacientes del estudio de Framingham (con identidades y algunas analíticas sintéticas). Incluye búsqueda, filtros, ordenación, fichas individuales, historial de pruebas, gráficas, indicadores, hallazgos y notas.

## Puesta en marcha (un solo comando)

Requisitos: **Docker Desktop**, **Node.js 20+** y el dataset en **`data/raw.csv`** (no está en git: cópialo ahí). Python no hace falta: el script instala [uv](https://docs.astral.sh/uv/) y uv trae el Python correcto.

| Sistema | Comando (desde la raíz del repositorio) |
| --- | --- |
| Windows | doble clic en `setup.cmd`, o `powershell -ExecutionPolicy Bypass -File setup.ps1` |
| macOS / Linux | `./setup.sh` |

El script ([scripts/bootstrap.py](scripts/bootstrap.py)) hace todo y deja la app en marcha en [http://localhost:5173](http://localhost:5173) hasta Ctrl+C:

1. Comprueba los requisitos (arranca Docker si está parado).
2. Instala las dependencias de Python de `backend/` y `ml/`.
3. Crea y arranca la base de datos (contenedor `cardia-db`, datos en el volumen `cardia-db-data`).
4. Construye las fuentes desde `raw.csv`, carga la base de datos con el ETL, calcula los hallazgos y el índice KNN.
5. Arranca el Motor de Riesgo (8001), el backend (8000) y el frontend (5173).
6. Calcula el riesgo de todos los pacientes y genera e ingesta las analíticas PDF.

La primera vez tarda unos 30 minutos (sobre todo los pasos 6). Volver a ejecutarlo es rápido: salta lo que ya está hecho y solo arranca los servicios. Registros en `logs/`.

| Opción | Para qué |
| --- | --- |
| `--reset` | Vaciar y recargar la base de datos desde cero |
| `--skip-pdfs` | No generar ni ingestar las analíticas PDF |
| `--no-serve` | Prepararlo todo y terminar sin dejar los servicios en marcha |
| `--check` | Al final, ejecutar el smoke test de la base de datos y todas las pruebas |
| `--db-port`, `--api-port`, `--ml-port`, `--web-port`, `--db-container` | Cambiar puertos o el nombre del contenedor |

## Ejecutar a mano

Hacen falta cuatro piezas en marcha:

1. La base de datos cargada con el ETL (`build_sources` una vez y `load_sources --reset`): ver [db/README.md](db/README.md).
2. El Motor de Riesgo + XAI (modelo de ML), ver [ml/README.md](ml/README.md):

   ```sh
   cd ml
   uv run uvicorn service:app --port 8001
   ```

3. El backend (Python 3.11+ y [uv](https://docs.astral.sh/uv/)), apuntando al Motor de Riesgo:

   ```sh
   cd backend
   CARDIA_ML_RISK_URL=http://127.0.0.1:8001 uv run uvicorn app.main:app --port 8000
   ```

   La primera vez, calcula la predicción de todos los pacientes: `CARDIA_ML_RISK_URL=http://127.0.0.1:8001 uv run python -m app.jobs.backfill_risk` (unos 12 minutos).

4. El frontend (Node.js 20 o posterior), desde la raíz del repositorio:

   ```sh
   node scripts/serve.mjs
   ```

Abre [http://localhost:5173](http://localhost:5173). El servidor del frontend entrega los archivos estáticos y reenvía `/api/*` al backend (`http://127.0.0.1:8000`; cámbialo con `CARDIA_API_URL`). No hace falta instalar paquetes de Node. También puedes usar `npm run dev`.

En Windows, si el repositorio está en una ruta UNC de WSL, ejecuta directamente `node scripts/serve.mjs` desde PowerShell; así evitas la restricción de rutas UNC de CMD al ejecutar scripts npm. Desde WSL necesitas una instalación de Node disponible en esa distribución.

## Backend y datos

- [db/](db/README.md): esquema PostgreSQL + TimescaleDB + pgvector; fuentes de datos separadas por origen y ETL que las carga.
- [backend/](backend/README.md): Core Backend API (FastAPI) con los endpoints del frontend, el motor de reglas (`finding-rules.json`) y la API interna para los servicios de ML.
- [ml/](ml/README.md): modelo de riesgo cardiovascular (Cox entrenado por el equipo con Framingham), su servicio con explicación SHAP y el reentrenamiento periódico.

El frontend lee del backend los datos de la base de datos: identidad, contacto, antecedentes, mediciones, línea temporal, notas, seguimiento y la predicción de riesgo del modelo con las variables que la explican.

## Configuración clínica

- [Indicadores y columnas](src/config/indicators.json): nombres, claves de datos, unidades, decimales, orden de las filas y columnas del resumen.
- [Reglas de hallazgos](src/config/finding-rules.json): añade, modifica o desactiva alertas sin editar el frontend.
- [Contrato de datos y configuración](docs/data-contract.md): estructura de las mediciones y ejemplos de reglas.
- [Datos ficticios](src/data/demo/): los 24 pacientes de ejemplo que usan las pruebas de `tests/`.
- [Arquitectura del frontend](docs/arquitectura.md): qué hay en cada carpeta, cómo fluye la información y cómo conectar el backend.

El campo `field` de un indicador y de una regla identifica la misma variable dentro de `patient.measurements` y coincide con `indicator.code` en la base de datos.

## Comprobar

```sh
node scripts/check.mjs
```

Comprueba la sintaxis de los módulos y ejecuta las pruebas de búsqueda, filtros, historiales, cambios, reglas, datos ausentes y categorías KDIGO. También está disponible `npm run check`.

## Notas de la demo

El riesgo es la probabilidad de evento cardiovascular a 10 años de un modelo de Cox (AUC de test 0,66) entrenado con un dataset docente: no está validado para uso clínico. Las reglas de hallazgos usan umbrales ilustrativos pendientes de validación clínica. Las categorías G/A de KDIGO se obtienen de eGFR y ACR y no establecen un diagnóstico de enfermedad renal crónica.

Las notas de consulta y el seguimiento se guardan en el servidor. Los ajustes de la clasificación de riesgo se guardan en `localStorage`; se pueden restablecer desde “Acerca de la demo”. Los hallazgos los calcula el frontend con las mismas reglas que el backend.

Las instrucciones originales del repositorio de la hackathon se conservan en [docs/hackathon-repository.md](docs/hackathon-repository.md).
