"""API interna para los servicios de ML (4A entrenamiento, 4B serving).

Protegida con X-API-Key. Así ningún servicio de ML necesita credenciales de
la base de datos: leen y escriben solo a través de estos endpoints.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import risk_service
from ..deps import Conn, PatientId, require_ml_key
from ..formatting import iso
from ..schemas import EmbeddingSearchIn, EmbeddingsIn, PredictionIn

router = APIRouter(prefix="/ml", tags=["ml (interno)"], dependencies=[Depends(require_ml_key)])

OUTCOME_COLUMNS = {
    "cv": ("cvd", "days_to_cvd"),
    "chd": ("any_chd", "days_to_any_chd"),
    "stroke": ("stroke", "days_to_stroke"),
    "death": ("death", "days_to_death"),
    "hypertension": ("hypertension", "days_to_hypertension"),
}


def _jsonable(row: dict) -> dict:
    return {k: (iso(v) if isinstance(v, datetime) else v) for k, v in row.items()}


@router.get("/training-set")
def training_set(
    conn: Conn,
    target: Literal["cv", "chd", "stroke", "death", "hypertension"] = "cv",
    limit: int = Query(5_000, ge=1, le=20_000),
    after_patient_id: int | None = Query(None, description="Cursor: último patient_id de la página anterior"),
    after_exam_time: datetime | None = None,
):
    """Una fila por examen: variables (exam_features) + etiqueta del objetivo (4A).

    `event` y `days_to_event` cuentan desde el examen, no desde la línea base:
    days_to_event = días hasta el evento (o la censura) - days_since_baseline.
    Los exámenes posteriores al evento se excluyen.
    """
    flag, days = OUTCOME_COLUMNS[target]
    params: dict = {"limit": limit}
    cursor_sql = ""
    if after_patient_id is not None:
        if after_exam_time is None:
            raise HTTPException(422, "after_exam_time es obligatorio junto a after_patient_id")
        cursor_sql = "AND (f.patient_id, f.exam_time) > (%(pid)s, %(et)s)"
        params |= {"pid": after_patient_id, "et": after_exam_time}
    rows = conn.execute(f"""
        SELECT f.*, o.{flag} AS event, o.{days} - f.days_since_baseline AS days_to_event
        FROM exam_features f JOIN patient_outcome o USING (patient_id)
        WHERE o.{days} >= f.days_since_baseline {cursor_sql}
        ORDER BY f.patient_id, f.exam_time
        LIMIT %(limit)s
    """, params).fetchall()
    items = [_jsonable(r) for r in rows]
    nxt = ({"after_patient_id": rows[-1]["patient_id"], "after_exam_time": iso(rows[-1]["exam_time"])}
           if len(rows) == limit else None)
    return {"target": target, "items": items, "next": nxt}


@router.get("/patients/{patient_id}/features")
def serving_features(patient_id: PatientId, conn: Conn):
    """Variables actuales del paciente para predecir (4B). Sin etiquetas."""
    exam_time, features = risk_service.build_features(conn, patient_id)
    return {"patientId": str(patient_id), "inputExamTime": iso(exam_time), "features": features}


@router.post("/patients/{patient_id}/risk-predictions", status_code=201)
def save_prediction(patient_id: PatientId, body: PredictionIn, conn: Conn):
    """El Motor de Riesgo guarda una predicción (por ejemplo, un recálculo masivo tras promocionar un modelo)."""
    exam_time = body.inputExamTime
    if exam_time is None:
        exam_time, _ = risk_service.build_features(conn, patient_id)
    pred = risk_service.Prediction(**body.model_dump(exclude={"target", "trigger"}))
    try:
        return risk_service.store(conn, patient_id, body.target, pred, trigger=body.trigger,
                                  sent_features=body.features, input_exam_time=exam_time)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


def _vector(values: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


@router.put("/embeddings")
def upsert_embeddings(body: EmbeddingsIn, conn: Conn):
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO exam_embedding (patient_id, exam_time, embedding_version, embedding)
            VALUES (%s, %s, %s, %s::vector)
            ON CONFLICT (patient_id, exam_time, embedding_version)
            DO UPDATE SET embedding = EXCLUDED.embedding, created_at = now()
        """, [(i.patientId, i.examTime, body.version, _vector(i.embedding)) for i in body.items])
    return {"version": body.version, "upserted": len(body.items)}


@router.post("/embeddings/search")
def search_embeddings(body: EmbeddingSearchIn, conn: Conn):
    """KNN sobre el índice HNSW: exámenes más parecidos de otros pacientes."""
    vec = _vector(body.embedding)
    rows = conn.execute("""
        SELECT patient_id, exam_time, embedding <-> %(v)s::vector AS distance
        FROM exam_embedding
        WHERE embedding_version = %(ver)s
          AND (%(ex)s::bigint IS NULL OR patient_id <> %(ex)s::bigint)
        ORDER BY embedding <-> %(v)s::vector
        LIMIT %(k)s
    """, {"v": vec, "ver": body.version, "ex": body.excludePatientId, "k": body.k}).fetchall()
    return [{"patientId": str(r["patient_id"]), "examTime": iso(r["exam_time"]),
             "distance": r["distance"]} for r in rows]


@router.get("/embeddings/{patient_id}")
def patient_embeddings(patient_id: PatientId, conn: Conn, version: str):
    rows = conn.execute("""
        SELECT exam_time, embedding::text AS embedding FROM exam_embedding
        WHERE patient_id = %s AND embedding_version = %s ORDER BY exam_time
    """, [patient_id, version]).fetchall()
    return [{"examTime": iso(r["exam_time"]), "embedding": json.loads(r["embedding"])} for r in rows]
