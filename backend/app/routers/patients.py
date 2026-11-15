"""Endpoints que consume el frontend (src/services/api-client.js)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from psycopg import errors

from .. import findings_service, patients_service, risk_service
from ..deps import AppSettings, Clinician, Config, Conn, PatientId
from ..formatting import iso, risk_level, risk_percent
from ..knn import service as knn_service
from ..schemas import FollowupIn, NewTestIn, NoteIn, RiskClassificationIn

router = APIRouter(prefix="/patients", tags=["pacientes"])


@router.get("")
def list_patients(
    conn: Conn,
    q: str | None = Query(None, description="Busca en nombre y CIP, sin distinguir tildes"),
    risk: Literal["high", "medium", "low"] | None = Query(None, description="Clasificación final (con ajuste clínico)"),
    sex: str | None = Query(None, description="Hombre/Mujer o M/F"),
    condition: str | None = Query(None, description="Etiqueta de antecedente, p. ej. Hipertensión"),
    age: Literal["65plus", "under65"] | None = None,
    followup: bool | None = None,
    sort: Literal["risk-desc", "risk-asc", "name", "age", "recent"] = "risk-desc",
    limit: int = Query(50, ge=1, le=5_000, description="Hasta 5.000: el frontend carga el cupo completo"),
    offset: int = Query(0, ge=0),
    include_measurements: bool = Query(True, description="Añade measurements a cada paciente de la página"),
):
    result = patients_service.list_patients(
        conn, q=q, risk=risk, sex=sex, condition=condition, age=age, followup=followup,
        sort=sort, limit=limit, offset=offset, include_measurements=include_measurements)
    # Todo son tipos JSON nativos: se evita jsonable_encoder, que con el cupo completo
    # (~12 MB) tardaba más que la consulta.
    return Response(json.dumps(result, ensure_ascii=False), media_type="application/json")


@router.get("/{patient_id}")
def get_patient(patient_id: PatientId, conn: Conn, config: Config):
    return patients_service.get_patient(conn, patient_id, config)


@router.get("/{patient_id}/measurements")
def get_measurements(patient_id: PatientId, conn: Conn):
    """{ field: [{ value, date, unit, source }] } (docs/data-contract.md)."""
    return patients_service.measurements_for(conn, [patient_id]).get(patient_id, {})


@router.get("/{patient_id}/events")
def get_events(patient_id: PatientId, conn: Conn):
    return patients_service.events_for(conn, patient_id)


@router.get("/{patient_id}/findings")
def get_findings(patient_id: PatientId, conn: Conn, config: Config):
    """Hallazgos activos guardados por el motor de reglas."""
    return findings_service.active_for(conn, patient_id, config)


@router.get("/{patient_id}/risk-assessments")
def get_risk_assessments(patient_id: PatientId, conn: Conn,
                         target: Literal["cv", "diabetes", "renal"] | None = None):
    """Predicciones guardadas, de la más reciente a la más antigua."""
    return patients_service.risk_assessments(conn, patient_id, target)


@router.post("/{patient_id}/risk-assessments/recalculate")
def recalculate_risk(patient_id: PatientId, conn: Conn, settings: AppSettings):
    return {"risk": risk_service.recalculate(conn, patient_id, settings, trigger="manual")}


# --- Pacientes similares (KNN) --------------------------------------------------

@router.get("/{patient_id}/similar")
def similar_patients(
    patient_id: PatientId, conn: Conn,
    include_latest: bool = Query(False, description="false: estado en la penúltima prueba (por defecto); "
                                                    "true: estado con la última prueba"),
    k: int = Query(7, ge=1, le=20),
):
    """Los k pacientes cuyo estado en algún examen histórico más se parece al de este paciente,
    con sus valores, diferencias y qué les pasó después."""
    try:
        return knn_service.find_similar(conn, patient_id, include_latest=include_latest, k=k)
    except knn_service.KnnNotReady as exc:
        raise HTTPException(503, str(exc))
    except knn_service.NotEnoughTests as exc:
        raise HTTPException(409, str(exc))


# --- Ajuste clínico de la clasificación ---------------------------------------

@router.put("/{patient_id}/risk-classification")
def set_risk_classification(patient_id: PatientId, body: RiskClassificationIn, conn: Conn, author: Clinician):
    """El médico cambia el nivel (nunca la probabilidad). Si elige el del modelo, se elimina el ajuste."""
    latest = conn.execute("""
        SELECT probability FROM risk_prediction WHERE patient_id = %s AND target = 'cv'
        ORDER BY predicted_at DESC LIMIT 1
    """, [patient_id]).fetchone()
    if latest is None:
        raise HTTPException(409, "El paciente no tiene predicción de riesgo que ajustar")
    model_level = risk_level(risk_percent(latest["probability"]))
    conn.execute("""UPDATE risk_classification_override SET cleared_at = now()
                    WHERE patient_id = %s AND cleared_at IS NULL""", [patient_id])
    if body.level == model_level:
        return {"riskOverride": None, "effectiveRiskLevel": model_level}
    if not body.reason.strip():
        raise HTTPException(422, "El motivo es obligatorio cuando la clasificación no coincide con la del modelo")
    row = conn.execute("""
        INSERT INTO risk_classification_override (patient_id, level, model_level, reason, author)
        VALUES (%s, %s, %s, %s, %s) RETURNING *
    """, [patient_id, body.level, model_level, body.reason.strip(), author]).fetchone()
    override = {"level": row["level"], "reason": row["reason"], "author": row["author"],
                "date": iso(row["created_at"]), "modelLevel": row["model_level"]}
    return {"riskOverride": override, "effectiveRiskLevel": row["level"]}


@router.delete("/{patient_id}/risk-classification", status_code=204)
def clear_risk_classification(patient_id: PatientId, conn: Conn):
    conn.execute("""UPDATE risk_classification_override SET cleared_at = now()
                    WHERE patient_id = %s AND cleared_at IS NULL""", [patient_id])
    return Response(status_code=204)


# --- Seguimiento --------------------------------------------------------------

@router.put("/{patient_id}/followup")
def set_followup(patient_id: PatientId, body: FollowupIn, conn: Conn, author: Clinician):
    conn.execute("""
        INSERT INTO patient_followup (patient_id, followup, updated_by) VALUES (%s, %s, %s)
        ON CONFLICT (patient_id) DO UPDATE
        SET followup = EXCLUDED.followup, updated_by = EXCLUDED.updated_by, updated_at = now()
    """, [patient_id, body.followup, author])
    return {"followup": body.followup}


# --- Notas --------------------------------------------------------------------

@router.get("/{patient_id}/notes")
def get_notes(patient_id: PatientId, conn: Conn):
    return patients_service.notes_for(conn, patient_id)


@router.post("/{patient_id}/notes", status_code=201)
def create_note(patient_id: PatientId, body: NoteIn, conn: Conn, author: Clinician):
    row = conn.execute("""
        INSERT INTO clinical_note (patient_id, text, author) VALUES (%s, %s, %s) RETURNING *
    """, [patient_id, body.text, author]).fetchone()
    return patients_service.note_dict(row)


@router.put("/{patient_id}/notes/{note_id}")
def update_note(patient_id: PatientId, note_id: UUID, body: NoteIn, conn: Conn):
    row = conn.execute("""
        UPDATE clinical_note SET text = %s, updated_at = now()
        WHERE note_id = %s AND patient_id = %s RETURNING *
    """, [body.text, note_id, patient_id]).fetchone()
    if row is None:
        raise HTTPException(404, "Nota no encontrada")
    return patients_service.note_dict(row)


# --- Evento "Nueva prueba" ----------------------------------------------------

@router.post("/{patient_id}/tests", status_code=201)
def new_test(patient_id: PatientId, body: NewTestIn, conn: Conn, config: Config, settings: AppSettings):
    """Guarda resultados nuevos, evalúa las reglas y pide el riesgo al ML (flujo 1 del diagrama)."""
    taken_at = body.takenAt or datetime.now(timezone.utc)
    if taken_at.tzinfo is None:
        taken_at = taken_at.replace(tzinfo=timezone.utc)
    if taken_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "takenAt no puede estar en el futuro")

    known = {r["code"]: r for r in conn.execute("SELECT code, kind, label FROM indicator")}
    unknown = sorted(set(body.values) - set(known))
    if unknown:
        raise HTTPException(422, f"Indicadores desconocidos: {', '.join(unknown)}")

    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO measurement (patient_id, indicator_code, measured_at, value, source, document_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, [(patient_id, code, taken_at, value, body.source, body.documentId)
                      for code, value in body.values.items()])
            is_lab = any(known[c]["kind"] == "lab" for c in body.values)
            conn.execute("""
                INSERT INTO clinical_event (patient_id, event_time, event_type, title, description, document_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [patient_id, taken_at, "laboratory" if is_lab else "exploration",
                  body.title or ("Nueva analítica" if is_lab else "Nueva exploración"),
                  ", ".join(known[c]["label"] for c in body.values), body.documentId])
    except errors.UniqueViolation:
        raise HTTPException(409, "Ya existe una medición de ese indicador en ese instante")
    except errors.ForeignKeyViolation:
        raise HTTPException(422, "documentId no existe")

    stats = findings_service.refresh(conn, config, [patient_id])
    risk = (risk_service.recalculate(conn, patient_id, settings, trigger="new_test")
            if body.recalculateRisk else [])
    return {
        "patientId": str(patient_id),
        "takenAt": iso(taken_at),
        "stored": sorted(body.values),
        "findings": {
            "created": stats.created,
            "resolved": stats.resolved,
            "active": findings_service.active_for(conn, patient_id, config),
        },
        "risk": risk,
    }
