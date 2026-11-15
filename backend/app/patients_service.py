"""Monta los pacientes con el contrato del frontend (docs/data-contract.md)."""
from __future__ import annotations

from collections import defaultdict

from psycopg import Connection
from psycopg.rows import tuple_row

from . import findings_service
from .clinical_tests import TEST_KINDS
from .clinical_config import ClinicalConfig
from .formatting import SEX_LABELS, initials, iso, normalize_text, risk_level, risk_percent

# Etiquetas que usa el filtro del listado (src/ui/views/patient-list.js).
# Se derivan de los datos disponibles; son marcadores de la demo, no diagnósticos.
CONDITION_RULES = {
    "Hipertensión": "prev_hypertension (PREVHYP del último examen)",
    "Diabetes tipo 2": "diabetes (DIABETES del último examen; raw.csv no distingue el tipo)",
    "Enf. renal crónica": "último eGFR < 60 o último ACR >= 30 (criterios KDIGO, sin confirmar persistencia)",
    "Dislipidemia": "último colesterol total >= 240 o LDL >= 160 mg/dL",
    "Tabaquismo": "current_smoker (CURSMOKE del último examen)",
}

EVENT_TYPES = {
    "exam": ("Exploración", "activity"),
    "laboratory": ("Laboratorio", "flask"),
    "exploration": ("Exploración", "activity"),
    "treatment": ("Tratamiento", "pill"),
    "history": ("Antecedente", "clipboard"),
}

_BASE_SQL = """
    SELECT o.*, p.birth_year, p.phone, p.email, p.education_level,
           ro.model_level AS risk_override_model_level, ro.author AS risk_override_author,
           ro.created_at AS risk_override_at
    FROM patient_overview o
    JOIN patient p USING (patient_id)
    LEFT JOIN risk_classification_override ro
           ON ro.patient_id = o.patient_id AND ro.cleared_at IS NULL
"""


def _conditions(row: dict, latest: dict[str, float]) -> list[str]:
    out = []
    if row["prev_hypertension"]:
        out.append("Hipertensión")
    if row["diabetes"]:
        out.append("Diabetes tipo 2")
    if latest.get("egfr", 999) < 60 or latest.get("acr", 0) >= 30:
        out.append("Enf. renal crónica")
    if latest.get("total_cholesterol", 0) >= 240 or latest.get("ldl", 0) >= 160:
        out.append("Dislipidemia")
    if row["current_smoker"]:
        out.append("Tabaquismo")
    return out


def _override(row: dict) -> dict | None:
    if not row["risk_override_level"]:
        return None
    return {
        "level": row["risk_override_level"],
        "reason": row["risk_override_reason"],
        "author": row["risk_override_author"],
        "date": iso(row["risk_override_at"]),
        "modelLevel": row["risk_override_model_level"],
    }


def _summary(row: dict, latest: dict[str, float]) -> dict:
    risk = risk_percent(row["cv_risk"])
    model_level = risk_level(risk)
    override = _override(row)
    first, last = row["first_name"], row["last_name"]
    return {
        "id": str(row["patient_id"]),
        "cip": row["cip"],
        "firstName": first,
        "lastName": last,
        "name": " ".join(x for x in (first, last) if x) or f"Paciente {row['patient_id']}",
        "initials": initials(first, last),
        "age": row["age"],
        "sex": SEX_LABELS.get(row["sex"], row["sex"]),
        "sexCode": row["sex"],
        "risk": risk,
        "riskLevel": model_level,
        "effectiveRiskLevel": override["level"] if override else model_level,
        "riskAt": iso(row["cv_risk_at"]),
        "riskModelVersion": row["cv_risk_model_version"],
        "riskOverride": override,
        "followup": row["followup"],
        "lastTest": iso(row["last_test"]),
        "conditions": _conditions(row, latest),
        "activeFindings": row["active_findings"],
    }


def _latest_values(conn: Connection, ids: list[int] | None, codes: list[str]) -> dict[int, dict[str, float]]:
    sql = "SELECT patient_id, indicator_code, value FROM latest_measurement WHERE indicator_code = ANY(%s)"
    params: list = [codes]
    if ids is not None:
        sql += " AND patient_id = ANY(%s)"
        params.append(ids)
    out: dict[int, dict[str, float]] = defaultdict(dict)
    for r in conn.execute(sql, params):
        out[r["patient_id"]][r["indicator_code"]] = r["value"]
    return out


def measurements_for(conn: Connection, ids: list[int]) -> dict[int, dict[str, list[dict]]]:
    """{patient_id: {field: [{value, date, unit}]}} ordenado por fecha.

    La fecha se formatea en SQL (misma regla que formatting.iso: día si es medianoche UTC,
    instante si no) y se leen tuplas: con el cupo completo son ~120.000 filas.
    """
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("""
            SELECT m.patient_id, m.indicator_code, m.value, i.unit, m.source,
                   CASE WHEN (m.measured_at AT TIME ZONE 'UTC')::time = '00:00'
                        THEN to_char(m.measured_at AT TIME ZONE 'UTC', 'YYYY-MM-DD')
                        ELSE to_char(m.measured_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                   END
            FROM measurement m JOIN indicator i ON i.code = m.indicator_code
            WHERE m.patient_id = ANY(%s)
            ORDER BY m.patient_id, m.indicator_code, m.measured_at
        """, [ids])
        out: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for pid, code, value, unit, source, date in cur:
            out[pid][code].append({"value": value, "date": date, "unit": unit, "source": source})
    return out


CONDITION_CODES = ["egfr", "acr", "total_cholesterol", "ldl"]

# Pacientes sin predicción de riesgo van siempre al final.
SORTS = {
    "risk-desc": lambda p: (p["risk"] is None, -(p["risk"] or 0)),
    "risk-asc": lambda p: (p["risk"] is None, p["risk"] or 0),
    "name": lambda p: normalize_text(p["name"]),
    "age": lambda p: -(p["age"] or 0),
    # Fecha ISO comparada como texto: la más reciente primero (se ordena al revés).
    "recent": lambda p: p["lastTest"] or "",
}
REVERSED_SORTS = {"recent"}


def list_patients(conn: Connection, *, q: str | None, risk: str | None, sex: str | None,
                  condition: str | None, age: str | None, followup: bool | None,
                  sort: str, limit: int, offset: int, include_measurements: bool) -> dict:
    """Listado con los mismos filtros y órdenes que src/domain/patient-filters.js, paginado."""
    rows = conn.execute(_BASE_SQL).fetchall()
    latest = _latest_values(conn, None, CONDITION_CODES)
    items = [_summary(r, latest.get(r["patient_id"], {})) for r in rows]

    query = normalize_text(q or "").strip()
    sex_code = {"hombre": "M", "mujer": "F", "m": "M", "f": "F"}.get((sex or "").lower())

    def keep(p: dict) -> bool:
        return ((not query or query in normalize_text(f"{p['name']} {p['cip'] or ''}"))
                and (not risk or p["effectiveRiskLevel"] == risk)
                and (not sex_code or p["sexCode"] == sex_code)
                and (not condition or condition in p["conditions"])
                and (not age or (p["age"] is not None and (p["age"] >= 65 if age == "65plus" else p["age"] < 65)))
                and (followup is None or p["followup"] == followup))

    selected = sorted(filter(keep, items), key=SORTS[sort], reverse=sort in REVERSED_SORTS)
    page = selected[offset:offset + limit]
    if include_measurements and page:
        ms = measurements_for(conn, [int(p["id"]) for p in page])
        for p in page:
            p["measurements"] = ms.get(int(p["id"]), {})
    return {"items": page, "total": len(selected), "limit": limit, "offset": offset}


def get_patient(conn: Connection, patient_id: int, config: ClinicalConfig) -> dict | None:
    row = conn.execute(_BASE_SQL + " WHERE o.patient_id = %s", [patient_id]).fetchone()
    if row is None:
        return None
    latest = _latest_values(conn, [patient_id], CONDITION_CODES).get(patient_id, {})
    patient = _summary(row, latest)
    patient.update({
        "phone": row["phone"],
        "email": row["email"],
        "birthYear": row["birth_year"],
        "educationLevel": row["education_level"],
        "measurements": measurements_for(conn, [patient_id]).get(patient_id, {}),
        "events": events_for(conn, patient_id),
        "notes": notes_for(conn, patient_id),
        "findings": findings_service.active_for(conn, patient_id, config),
    })
    history = risk_assessments(conn, patient_id, target="cv")
    patient["history"] = {"risk": [h["risk"] for h in reversed(history)],
                          "riskDates": [h["predictedAt"] for h in reversed(history)]}
    patient["factors"] = history[0]["factors"] if history else []
    patient["shapTopK"] = history[0]["shapTopK"] if history else []
    return patient


def events_for(conn: Connection, patient_id: int) -> list[dict]:
    """Línea temporal. Cada evento de prueba trae sus propios resultados (solo los de su tipo)."""
    rows = conn.execute("""
        SELECT event_id, event_time, event_type, title, description, test_kind, document_id
        FROM clinical_event WHERE patient_id = %s ORDER BY event_time DESC
    """, [patient_id]).fetchall()
    values = {(r["measured_at"], r["indicator_code"]): r for r in conn.execute("""
        SELECT m.measured_at, m.indicator_code, m.value, i.label, i.unit, i.decimals
        FROM measurement m JOIN indicator i ON i.code = m.indicator_code
        WHERE m.patient_id = %s
    """, [patient_id])}
    out = []
    for r in rows:
        kind = TEST_KINDS.get(r["test_kind"])
        if kind:
            label, icon = kind.label, kind.icon
            results = [{"field": c, "label": values[(r["event_time"], c)]["label"],
                        "value": values[(r["event_time"], c)]["value"],
                        "unit": values[(r["event_time"], c)]["unit"],
                        "decimals": values[(r["event_time"], c)]["decimals"]}
                       for c in kind.codes if (r["event_time"], c) in values]
        else:
            label, icon = EVENT_TYPES.get(r["event_type"], ("Otro", "clipboard"))
            results = []
        out.append({"id": str(r["event_id"]), "date": iso(r["event_time"]), "title": r["title"],
                    "type": label, "eventType": r["event_type"], "testKind": r["test_kind"], "icon": icon,
                    "description": r["description"] or "", "results": results,
                    "documentId": str(r["document_id"]) if r["document_id"] else None})
    return out


def notes_for(conn: Connection, patient_id: int) -> list[dict]:
    rows = conn.execute("""
        SELECT note_id, text, author, created_at, updated_at
        FROM clinical_note WHERE patient_id = %s ORDER BY updated_at DESC
    """, [patient_id])
    return [note_dict(r) for r in rows]


def note_dict(r: dict) -> dict:
    return {"id": str(r["note_id"]), "text": r["text"], "author": r["author"],
            "date": iso(r["updated_at"]), "createdAt": iso(r["created_at"])}


def _factors(shap: list[dict]) -> list[dict]:
    """shap_top_k -> factors del frontend: [{label, value, weight}] con weight 0-100 relativo al mayor."""
    if not shap:
        return []
    top = max(abs(f.get("contribution", 0)) for f in shap) or 1
    out = []
    for f in shap:
        value = f.get("value")
        unit = f.get("unit")
        if value is None:
            shown = "Sin dato"           # el modelo lo imputó (p. ej. HDL fuera del tercer examen)
        elif isinstance(value, (int, float)):
            shown = f"{value:g} {unit}".strip()
        else:
            shown = str(value)
        out.append({
            "label": f.get("label") or f.get("feature"),
            "value": shown,
            "contribution": f.get("contribution", 0),
            "weight": round(abs(f.get("contribution", 0)) / top * 100),
            "direction": "up" if f.get("contribution", 0) >= 0 else "down",
        })
    return out


def risk_assessments(conn: Connection, patient_id: int, target: str | None = None) -> list[dict]:
    sql = "SELECT * FROM risk_prediction WHERE patient_id = %s"
    params: list = [patient_id]
    if target:
        sql += " AND target = %s"
        params.append(target)
    rows = conn.execute(sql + " ORDER BY predicted_at DESC", params).fetchall()
    return [{
        "target": r["target"],
        "probability": r["probability"],
        "risk": risk_percent(r["probability"]),
        "riskLevel": risk_level(risk_percent(r["probability"])),
        "predictedAt": iso(r["predicted_at"]),
        "horizonYears": r["horizon_years"],
        "modelName": r["model_name"],
        "modelVersion": r["model_version"],
        "trigger": r["trigger"],
        "inputExamTime": iso(r["input_exam_time"]),
        "shapBaseValue": r["shap_base_value"],
        "shapTopK": r["shap_top_k"],
        "factors": _factors(r["shap_top_k"]),
    } for r in rows]


def exists(conn: Connection, patient_id: int) -> bool:
    return conn.execute("SELECT 1 FROM patient WHERE patient_id = %s", [patient_id]).fetchone() is not None
