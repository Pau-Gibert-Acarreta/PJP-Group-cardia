"""Orquestación del riesgo: pide la predicción al microservicio 4B y la guarda.

Contrato con el Motor de Riesgo + XAI (4B):

    POST {CARDIA_ML_RISK_URL}/v1/predict
    { "patientId": "2448", "target": "cv", "inputExamTime": "...",
      "features": { "age_years": 52, "systolic": 121, ... } }

    200 { "probability": 0.25, "modelName": "cardia-cv", "modelVersion": "1.3.0",
          "horizonYears": 10, "shapBaseValue": 0.08,
          "shapTopK": [{ "feature": "systolic", "label": "PA sistólica",
                         "value": 121, "unit": "mmHg", "contribution": 0.04 }] }

El backend guarda cada respuesta en risk_prediction (append-only), que es a la
vez la última predicción del listado y el historial de la ficha.
"""
from __future__ import annotations

import json
from datetime import datetime

import httpx
from psycopg import Connection
from pydantic import BaseModel, Field

from .formatting import iso
from .settings import Settings


class Prediction(BaseModel):
    probability: float = Field(ge=0, le=1)
    modelName: str
    modelVersion: str
    horizonYears: int = Field(gt=0)
    shapBaseValue: float | None = None
    shapTopK: list[dict] = []
    features: dict | None = None       # si el servicio no lo devuelve, se guarda lo que se le envió
    inputExamTime: datetime | None = None


def build_features(conn: Connection, patient_id: int) -> tuple[datetime | None, dict]:
    """Variables para el modelo: estado del último examen, actualizado con pruebas posteriores.

    Igual que en el entrenamiento, cada valor es el de ese examen: un indicador que no se midió
    en el último examen queda ausente (lo imputa el modelo), no se rellena con uno antiguo.
    Las pruebas registradas después del examen (POST /tests) sí actualizan su valor.
    Nunca incluye patient_outcome: son etiquetas de entrenamiento (fuga de la variable objetivo).
    """
    exam = conn.execute("""
        SELECT * FROM exam_features WHERE patient_id = %s ORDER BY exam_time DESC LIMIT 1
    """, [patient_id]).fetchone()
    features: dict = {}
    exam_time = None
    if exam:
        exam_time = exam["exam_time"]
        features = {k: v for k, v in exam.items() if k not in ("patient_id", "exam_time")}
    for r in conn.execute("""
            SELECT indicator_code, value FROM latest_measurement
            WHERE patient_id = %s AND (%s::timestamptz IS NULL OR measured_at > %s::timestamptz)
        """, [patient_id, exam_time, exam_time]):
        features[r["indicator_code"]] = r["value"]
    return exam_time, features


def store(conn: Connection, patient_id: int, target: str, pred: Prediction, *,
          trigger: str, sent_features: dict, input_exam_time: datetime | None) -> dict:
    exam_time = pred.inputExamTime or input_exam_time
    if exam_time is None:
        raise ValueError("No hay examen de referencia para la predicción")
    row = conn.execute("""
        INSERT INTO risk_prediction (patient_id, target, predicted_at, model_name, model_version,
                                     probability, horizon_years, input_exam_time, trigger,
                                     features, shap_base_value, shap_top_k)
        VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING predicted_at
    """, [patient_id, target, pred.modelName, pred.modelVersion, pred.probability, pred.horizonYears,
          exam_time, trigger, json.dumps(pred.features or sent_features, default=str),
          pred.shapBaseValue, json.dumps(pred.shapTopK)]).fetchone()
    return {"target": target, "status": "stored", "probability": pred.probability,
            "modelVersion": pred.modelVersion, "predictedAt": iso(row["predicted_at"])}


def _post(url: str, payload: dict, timeout: float) -> dict:
    """Separado para poder sustituirlo en las pruebas."""
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def recalculate(conn: Connection, patient_id: int, settings: Settings, trigger: str = "new_test") -> list[dict]:
    """Pide y guarda una predicción por cada objetivo configurado. Nunca lanza: informa del estado."""
    if not settings.ml_risk_url:
        return [{"target": t, "status": "not_configured"} for t in settings.risk_targets]
    exam_time, features = build_features(conn, patient_id)
    results = []
    for target in settings.risk_targets:
        payload = {"patientId": str(patient_id), "target": target,
                   "inputExamTime": iso(exam_time), "features": features}
        try:
            data = _post(settings.ml_risk_url.rstrip("/") + "/v1/predict", payload, settings.ml_timeout_seconds)
            pred = Prediction.model_validate(data)
            with conn.transaction():  # savepoint: un error aquí no anula la prueba ya insertada
                results.append(store(conn, patient_id, target, pred, trigger=trigger,
                                     sent_features=features, input_exam_time=exam_time))
        except Exception as exc:  # el fallo del ML no debe perder la prueba ya guardada
            results.append({"target": target, "status": "failed", "error": str(exc)[:300]})
    return results
