# Cardia

Prototipo de una consulta de Atención Primaria para explorar el riesgo cardiovascular de los 4.434 pacientes del estudio de Framingham (con identidades y algunas analíticas sintéticas). Incluye búsqueda, filtros, ordenación, fichas individuales, historial de pruebas, gráficas, indicadores, hallazgos y notas.

## Ejecutar

Hacen falta tres piezas en marcha:

1. La base de datos cargada: ver [db/README.md](db/README.md).
2. El backend (Python 3.11+ y [uv](https://docs.astral.sh/uv/)):

   ```sh
   cd backend
   uv run uvicorn app.main:app --port 8000
   ```

3. El frontend (Node.js 20 o posterior), desde la raíz del repositorio:

   ```sh
   node scripts/serve.mjs
   ```

Abre [http://localhost:5173](http://localhost:5173). El servidor del frontend entrega los archivos estáticos y reenvía `/api/*` al backend (`http://127.0.0.1:8000`; cámbialo con `CARDIA_API_URL`). No hace falta instalar paquetes de Node. También puedes usar `npm run dev`.

En Windows, si el repositorio está en una ruta UNC de WSL, ejecuta directamente `node scripts/serve.mjs` desde PowerShell; así evitas la restricción de rutas UNC de CMD al ejecutar scripts npm. Desde WSL necesitas una instalación de Node disponible en esa distribución.

## Backend y datos

- [db/](db/README.md): esquema PostgreSQL + TimescaleDB + pgvector, carga de `raw.csv` y datos sintéticos.
- [backend/](backend/README.md): Core Backend API (FastAPI) con los endpoints del frontend, el motor de reglas (`finding-rules.json`) y la API interna para los servicios de ML.

El frontend lee del backend los datos de la base de datos: identidad, contacto, antecedentes, mediciones, línea temporal, notas y seguimiento. El riesgo de ML y sus variables explicativas siguen simulados en el navegador (`src/data/demo/simulated-risk.js`) hasta que exista el modelo.

## Configuración clínica

- [Indicadores y columnas](src/config/indicators.json): nombres, claves de datos, unidades, decimales, orden de las filas y columnas del resumen.
- [Reglas de hallazgos](src/config/finding-rules.json): añade, modifica o desactiva alertas sin editar el frontend.
- [Contrato de datos y configuración](docs/data-contract.md): estructura de las mediciones y ejemplos de reglas.
- [Datos ficticios](src/data/demo/): riesgo simulado y los 24 pacientes de ejemplo que usan las pruebas de `tests/`.
- [Arquitectura del frontend](docs/arquitectura.md): qué hay en cada carpeta, cómo fluye la información y cómo conectar el backend.

Las claves técnicas son provisionales porque todavía no se ha facilitado el esquema de la base de datos. El campo `field` de un indicador y de una regla identifica la misma variable dentro de `patient.measurements`. Cuando exista ese esquema, el adaptador de datos deberá entregar esas claves o se deberán actualizar los JSON. No hay ninguna conexión a una base de datos ni a un modelo de ML.

## Comprobar

```sh
node scripts/check.mjs
```

Comprueba la sintaxis de los módulos y ejecuta las pruebas de búsqueda, filtros, historiales, cambios, reglas, datos ausentes y categorías KDIGO. También está disponible `npm run check`.

## Notas de la demo

El riesgo y los factores explicativos están simulados. Las reglas de hallazgos usan umbrales ilustrativos pendientes de validación clínica. Las categorías G/A de KDIGO se obtienen de eGFR y ACR y no establecen un diagnóstico de enfermedad renal crónica.

Las notas de consulta y el seguimiento se guardan en el servidor. Los ajustes de la clasificación de riesgo se guardan en `localStorage`, porque el riesgo que ajustan es simulado; se pueden restablecer desde “Acerca de la demo”. Los hallazgos los calcula el frontend con las mismas reglas que el backend.

Las instrucciones originales del repositorio de la hackathon se conservan en [docs/hackathon-repository.md](docs/hackathon-repository.md).
