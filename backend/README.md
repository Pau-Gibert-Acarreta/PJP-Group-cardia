# Cardia Core Backend API

Bloque 5 de la arquitectura: API con FastAPI entre la base de datos, el motor de reglas y los servicios de ML. Ni el frontend ni los servicios de ML acceden a PostgreSQL: todo pasa por aquí.

```
Frontend (6) ──REST JSON──▶ /api/v1/patients, /api/v1/config ─┐
ML 4A / 4B   ──X-API-Key──▶ /api/v1/ml                         ├──▶ PostgreSQL + TimescaleDB + pgvector
Evento "Nueva prueba" ────▶ POST /api/v1/patients/{id}/tests ──┘      │
                                 │  1. guarda mediciones               │
                                 │  2. evalúa rules.json → finding     │
                                 └─ 3. pide riesgo a 4B → risk_prediction
```

## Ejecutar

Requiere Python 3.11+, [uv](https://docs.astral.sh/uv/) y la base de datos cargada (ver [db/README.md](../db/README.md)).

```sh
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

La documentación interactiva queda en <http://localhost:8000/docs>.

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `CARDIA_DATABASE_URL` | `postgresql://postgres:cardia@localhost:5432/cardia` | Conexión a la base de datos. |
| `CARDIA_RULES_PATH` | `src/config/finding-rules.json` | Reglas de hallazgos (`rules.json` en el diagrama). |
| `CARDIA_INDICATORS_PATH` | `src/config/indicators.json` | Indicadores y unidades. |
| `CARDIA_ML_RISK_URL` | sin definir | URL del Motor de Riesgo (4B). Sin ella no se calcula riesgo. |
| `CARDIA_ML_API_KEY` | sin definir | Clave para `/api/v1/ml`. Sin ella esos endpoints devuelven 503. |
| `CARDIA_RISK_TARGETS` | `["cv"]` | Objetivos que se piden a 4B tras una prueba nueva. |
| `CARDIA_CORS_ORIGINS` | `["http://localhost:5173", ...]` | Orígenes del frontend. |
| `CARDIA_DEFAULT_CLINICIAN` | `Dra. Carmen Vidal` | Autor de notas y ajustes si no llega la cabecera `X-Clinician`. |

También se pueden poner en `backend/.env`.

## Endpoints para el frontend

Mismas rutas que ya propone `src/services/api-client.js`, con prefijo `/api/v1`. Los pacientes salen con el contrato de [docs/data-contract.md](../docs/data-contract.md): `measurements[field] = [{ value, date, unit }]`, `risk` en porcentaje, `sex` como `Hombre`/`Mujer`.

| Método y ruta | Qué hace |
| --- | --- |
| `GET /patients` | Listado paginado. Filtros `q`, `risk`, `sex`, `condition`, `age` (`65plus`/`under65`), `followup`; orden `sort` (`risk-desc`, `risk-asc`, `name`, `age`, `recent`); `limit`, `offset`. Devuelve `{ items, total, limit, offset }`. |
| `GET /patients/{id}` | Ficha completa: datos, mediciones, eventos, notas, hallazgos activos, riesgo, `history.risk` y `factors`. |
| `GET /patients/{id}/measurements` | Solo las series. |
| `GET /patients/{id}/events` | Línea temporal. |
| `GET /patients/{id}/findings` | Hallazgos activos del motor de reglas. |
| `GET /patients/{id}/risk-assessments` | Predicciones guardadas (más reciente primero), con SHAP. |
| `POST /patients/{id}/risk-assessments/recalculate` | Pide de nuevo el riesgo a 4B. |
| `PUT / DELETE /patients/{id}/risk-classification` | Ajuste clínico del nivel `{ level, reason }`. Elegir el nivel del modelo elimina el ajuste. Queda el historial con autor y fecha. |
| `PUT /patients/{id}/followup` | `{ followup: true }`. |
| `GET / POST /patients/{id}/notes`, `PUT /patients/{id}/notes/{noteId}` | Notas de consulta `{ text }`. |
| `GET /patients/{id}/similar` | Los 7 pacientes más parecidos (KNN). `include_latest=false` (por defecto): estado en la penúltima prueba; `true`: con la última. Ver abajo. |
| `POST /patients/{id}/tests` | Evento "Nueva prueba" (ver abajo). |
| `GET /config/rules`, `GET /config/indicators` | Los JSON de configuración, para que el frontend los lea del backend. |
| `GET /config/conditions` | Cómo se deriva cada antecedente del listado. |
| `GET /health` | Comprueba la conexión a la base de datos. |

### Evento "Nueva prueba"

```sh
curl -X POST localhost:8000/api/v1/patients/2448/tests -H "Content-Type: application/json" \
  -d '{"takenAt": "2025-12-01T09:00:00Z", "source": "lab", "values": {"systolic": 140, "hba1c": 6.1}}'
```

Guarda una medición por valor y un evento en la línea temporal, recalcula los hallazgos del paciente y, si `CARDIA_ML_RISK_URL` está definida, pide y guarda el riesgo. Responde con lo guardado, los hallazgos creados, cerrados y activos, y el estado del riesgo (`stored`, `failed` o `not_configured`). Un fallo del ML no pierde la prueba.

## Motor de reglas

- Lee el mismo `finding-rules.json` que el frontend, con la misma validación y la misma semántica (`app/rules_engine.py` replica `src/domain/findings.js`): compara las dos últimas mediciones, métricas `current`, `previous`, `delta` y `percent_change`, todas las condiciones a la vez, `maxIntervalDays` opcional.
- Si el archivo cambia en disco, se relee en la siguiente petición. Un JSON inválido produce un error 500 visible en lugar de evaluar reglas sin validar.
- Los resultados se guardan en `finding`. Un hallazgo sigue activo mientras su regla se cumpla con las mismas dos mediciones. Si deja de cumplirse o la regla se desactiva, se cierra (`resolved_at`). Cada fila guarda `rules_version` (versión del JSON + hash).
- Para recalcular todos los pacientes después de cargar datos o cambiar las reglas:

  ```sh
  uv run python -m app.jobs.evaluate_findings
  ```

> Con los datos de Framingham no sale ningún hallazgo: entre dos exámenes del mismo paciente pasan al menos 1.554 días y todas las reglas tienen `maxIntervalDays: 180`. Los hallazgos aparecen cuando entran pruebas nuevas por `POST /tests`.

## Pacientes similares (KNN, k = 7)

`app/knn/` implementa el bloque 4B "KNN on-the-fly" dentro del backend.

- **Caso:** estado de un paciente en un instante t, con 20 variables, todas del dataset original de Framingham: contexto (edad, sexo, tabaco, diabetes, tratamiento, antecedentes), último valor de cada indicador hasta t (IMC, PA, frecuencia cardíaca, colesterol total y HDL, glucosa) y tendencia anual respecto a la medición anterior (PA sistólica, colesterol, IMC, glucosa). HbA1c, creatinina, eGFR y ACR no se usan porque son sintéticos.
- **Pesos:** más altos en los predictores clásicos de riesgo cardiovascular (edad 3; PA sistólica 2,5; sexo, tabaco, diabetes y cardiopatía previa 2; colesterol total y tendencia de PA 1,5). HDL pesa 0,75 porque en el estudio solo se midió en el tercer examen. Se cambian en `app/knn/features.py`.
- **Índice:** un vector por examen histórico (11.627), con desenlace conocido. Se construye con `uv run python -m app.jobs.build_knn_index` (unos 7 s) después de `db/005_knn.sql`.
- **Consulta:** sin la última prueba (lo que pide el frontend al abrir la ficha) o con ella (a petición del médico). HNSW devuelve los exámenes más cercanos y se queda el mejor de cada paciente hasta tener 7 pacientes distintos.
- **Respuesta:** variables del paciente y de cada caso, diferencia por variable en desviaciones estándar y desenlace después del examen comparado (evento cardiovascular, coronario, ictus, muerte, años de seguimiento). Los casos son anónimos ("Caso 1"…"Caso 7") porque son otros pacientes.

## API interna para ML (`/api/v1/ml`, cabecera `X-API-Key`)

| Método y ruta | Para |
| --- | --- |
| `GET /ml/training-set?target=cv` | 4A. Una fila por examen con las variables y la etiqueta (`event`, `days_to_event` contados desde ese examen). Excluye exámenes posteriores al evento. Paginado por cursor (`next`). |
| `GET /ml/patients/{id}/features` | 4B. Variables actuales del paciente: último examen + último valor de cada indicador. Nunca incluye etiquetas. |
| `POST /ml/patients/{id}/risk-predictions` | 4B guarda una predicción por su cuenta (p. ej. recálculo masivo tras promocionar un modelo). |
| `PUT /ml/embeddings` | Guarda vectores de 20 dimensiones por examen y versión. |
| `POST /ml/embeddings/search` | KNN sobre el índice HNSW (`{ version, embedding, k, excludePatientId }`). |
| `GET /ml/embeddings/{id}?version=` | Vectores de un paciente. |

### Contrato con el Motor de Riesgo (4B)

El backend llama a `POST {CARDIA_ML_RISK_URL}/v1/predict` con `{ patientId, target, inputExamTime, features }` y espera:

```json
{ "probability": 0.25, "modelName": "cardia-cv", "modelVersion": "1.3.0", "horizonYears": 10,
  "shapBaseValue": 0.08,
  "shapTopK": [{ "feature": "systolic", "label": "PA sistólica", "value": 121, "unit": "mmHg", "contribution": 0.04 }] }
```

## Pruebas

```sh
uv run pytest
```

- `tests/test_rules_engine.py`: motor de reglas y validación, sin base de datos.
- `tests/test_api.py`: todos los endpoints contra la base de datos cargada. Se omiten si no hay base de datos, y borran lo que escriben. El ML se sustituye por una respuesta simulada.

## Pendiente

- Autenticación de usuarios: hoy el autor llega en la cabecera `X-Clinician`.
- Documentos: servir PDFs con URL prefirmada cuando el compañero cargue `document`.
- Conectar el frontend: cambiar `patient-service.js` y `notes-service.js` para que usen `api-client.js`.
