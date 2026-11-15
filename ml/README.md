# Cardia ML: modelo de riesgo cardiovascular y XAI

Bloques 4A (entrenamiento periódico) y 4B (Motor de Riesgo + XAI) de la arquitectura, más el registro de modelos (bloque 3).

```
Base de datos ──load_raw()──▶ notebook 01 (bronze/silver/gold) ──▶ cardia_ml.train (4A) ──▶ models/ + registry.json
                                                                                              │ Champion
Core Backend ──POST /v1/predict──▶ service.py (4B): probabilidad a 10 años + SHAP ◀───────────┘
     └─ guarda la predicción en risk_prediction ──▶ frontend (riesgo, nivel y variables que lo explican)
```

## Modelo en producción (Champion)

`models/coxph_score2_v1.joblib`: el modelo entrenado por el equipo, **con sus pesos congelados**.

| | |
| --- | --- |
| Modelo | Cox de riesgos proporcionales (scikit-survival), alpha 0,1, ties Efron, con splines |
| Variables | Las 6 de SCORE2: edad, sexo, tabaquismo, presión sistólica, colesterol total y HDL (colesterol en mmol/L) |
| Objetivo | `target_broad_10y`: infarto, angina, enfermedad coronaria, ictus o CVD en los 10 años siguientes |
| Entrenamiento | Visitas 1-3 de los pacientes que no están en test, 40-69 años, sin diabetes ni cardiopatía o ictus previos (7.871 filas) |
| Métricas | AUC CV 0,6948 · AUC test 0,6636 (454 pacientes) |
| Elección | Mejor AUC de test entre los 5 mejores por CV de los 48 candidatos de `experiments/coxph/` |

Los candidatos 27 y 38 empatan en CV (0,69478 frente a 0,69475); se usa el 38, el que eligió el equipo por su AUC de test (0,6636 frente a 0,6617).

## Mismas variables que el CSV, ahora desde la base de datos

`cardia_ml.data.load_raw()` reconstruye desde PostgreSQL la tabla de `data/raw.csv`. Está comprobado (`tests/test_ml.py`):

- La tabla es **idéntica a `raw.csv`**: 39 columnas, 11.627 filas, ninguna celda distinta.
- La partición train/test da los **mismos 454 pacientes** de test.
- Reentrenar `experiments/coxph/best_pipeline.py` con esos datos reproduce **los coeficientes del modelo congelado** (diferencia < 1e-10) y su AUC de test.
- El modelo congelado reproduce **exactamente las 454 predicciones** de `experiments/coxph/test_predictions.csv`.

## Cómo se usa

Desde `ml/` (Python **3.12 o 3.13**, fijado en `.python-version`; [uv](https://docs.astral.sh/uv/) lo descarga si hace falta). El modelo congelado se guardó con scikit-learn 1.9.1 y scipy 1.18: con Python 3.11 se instala scipy 1.17 y el modelo no carga.

```sh
uv sync
uv run uvicorn service:app --port 8001                 # 4B: Motor de Riesgo + XAI
PYTHONPATH=src uv run python -m cardia_ml.train        # 4A: reentrena y promociona si mejora
uv run pytest                                          # pruebas (necesitan la base de datos cargada)
```

El backend necesita `CARDIA_ML_RISK_URL=http://127.0.0.1:8001`. Para calcular la predicción de todos los pacientes (desde `backend/`):

```sh
CARDIA_ML_RISK_URL=http://127.0.0.1:8001 uv run python -m app.jobs.backfill_risk
```

### Notebook

`notebooks/01_raw_bronze_silver.ipynb` (del equipo) genera bronze, silver y gold en `data/`. Ahora lee de la base de datos con `load_raw()`; el resto no cambia y da los mismos resultados (2.268 pacientes en silver, 1.812/454 en train/test). Para ejecutarlo:

```sh
uv sync --group notebook
cd notebooks && uv run jupyter nbconvert --to notebook --execute --inplace 01_raw_bronze_silver.ipynb
```

## Serving (`service.py`)

- `POST /v1/predict`: recibe las variables que envía el backend (`age_years`, `sex`, `current_smoker`, `systolic`, `total_cholesterol`, `hdl_cholesterol`, en las unidades de la app) y devuelve `probability` (evento en 10 años = 1 − S(10 años)), `modelVersion`, `shapBaseValue` y `shapTopK`.
- Las variables se pasan a las unidades del entrenamiento (sexo `male`/`female`, colesterol en mmol/L). Un valor ausente lo imputa el propio pipeline (mediana + indicador), igual que en el entrenamiento.
- Toma los valores del último examen; las pruebas posteriores (`POST /tests` del backend) los actualizan. No rellena huecos con mediciones antiguas.
- **SHAP**: valores exactos sobre las 6 variables (64 coaliciones, sin aproximar) del log-riesgo del Cox, con una muestra de 100 filas de entrenamiento como referencia. Cumplen que base + suma = log-riesgo del paciente. Se muestran en el frontend como «Variables que explican la estimación», con ↑ (aumenta) o ↓ (reduce).
- No accede a la base de datos.

## Reentrenamiento (`cardia_ml/train.py`)

Lee de la base de datos las mismas variables, reentrena el pipeline ganador (Challenger), lo evalúa en el test del notebook y solo lo promociona a Champion si mejora el AUC. Cada versión queda en `models/registry.json` con sus métricas. `--init` registra el modelo congelado del equipo.

## Archivos

| Ruta | Qué es |
| --- | --- |
| `src/pipeline_lib.py`, `src/pipeline_lib_pl.py`, `src/surv_models.py` | Módulos del equipo (los pickles los importan por nombre) |
| `src/cardia_ml/` | Datos desde la base de datos, modelo, SHAP y reentrenamiento |
| `experiments/coxph/` | Búsqueda del equipo: 48 candidatos, log, top 5, predicciones de test y pipeline ganador |
| `models/` | Modelo congelado, muestra de referencia para SHAP y registro |
| `notebooks/` | Preparación de datos (bronze/silver/gold) desde la base de datos |

## Limitaciones

- El modelo se entrenó con pacientes de 40 a 69 años; para edades fuera de ese rango la estimación es una extrapolación.
- El objetivo es un compuesto amplio (incluye angina), no el desenlace exacto de SCORE2.
- Framingham es un dataset docente; el modelo no está validado para uso clínico.
