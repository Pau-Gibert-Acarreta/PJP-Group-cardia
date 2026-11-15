"""Motor de Riesgo + XAI (bloque 4B): sirve el Champion congelado con SHAP local.

    uv run uvicorn service:app --port 8001          (desde ml/)

Contrato (el que ya usa backend/app/risk_service.py):

    POST /v1/predict
    { "patientId": "2448", "target": "cv", "inputExamTime": "...",
      "features": { "age_years": 52, "sex": "M", "current_smoker": false,
                    "systolic": 121, "total_cholesterol": 209, "hdl_cholesterol": 31, ... } }

    200 { "probability": 0.12, "modelName": "...", "modelVersion": "coxph_score2_v1",
          "horizonYears": 10, "shapBaseValue": -1.9, "shapTopK": [...], "features": {...} }

No accede a la base de datos: recibe las variables del Core Backend.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cardia_ml import data, explain  # noqa: E402
from cardia_ml.model import load  # noqa: E402



@asynccontextmanager
async def lifespan(_: FastAPI):
    load()  # carga el Champion una vez al arrancar
    yield


app = FastAPI(title="Cardia · Motor de Riesgo + XAI", version="0.1.0", lifespan=lifespan)


class PredictIn(BaseModel):
    patientId: str
    target: str = "cv"
    inputExamTime: str | None = None
    features: dict


def _clean(value):
    return None if isinstance(value, float) and math.isnan(value) else value


@app.get("/health")
def health():
    return {"status": "ok", "model": load().version}


@app.get("/v1/model")
def model_info():
    m = load()
    return {"name": m.name, "version": m.version, "metrics": m.metrics, "horizonYears": 10,
            "inputs": data.MODEL_FEATURES}


@app.post("/v1/predict")
def predict(body: PredictIn):
    if body.target != "cv":
        raise HTTPException(422, f"Objetivo no soportado: {body.target} (solo 'cv')")
    m = load()
    X = data.features_from_backend(body.features)
    if X["age"].isna().any() or X["sex"].isna().any():
        raise HTTPException(422, "Faltan edad o sexo, imprescindibles para el modelo")
    probability = float(m.probability(X)[0])
    base, phi = explain.shap_values(m.risk_score, X, m.background)
    used = {col: _clean(explain.describe(col, X.iloc[0][col])[1]) for col in X.columns}
    return {
        "probability": round(probability, 6),
        "modelName": m.name,
        "modelVersion": m.version,
        "horizonYears": 10,
        "shapBaseValue": round(base, 6),
        "shapTopK": explain.top_k(X, phi),
        "features": used,
    }
