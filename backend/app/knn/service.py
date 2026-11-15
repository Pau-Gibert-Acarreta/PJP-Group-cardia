"""Construcción del índice y búsqueda de los K pacientes más parecidos.

Índice: un vector por examen histórico (exam_embedding, versión knn-v1). Son
estados con desenlace conocido: el KNN busca pacientes que en algún examen se
parecían a este paciente ahora y cuenta qué les pasó después ("cohorte t-1").

Consulta, dos modos:
- without_latest (por defecto, al abrir la ficha): estado en la penúltima prueba.
- with_latest (a petición): estado en la última prueba.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime

from psycopg import Connection

from ..formatting import iso
from .features import (DIMENSIONS, FEATURES, INDICATOR_CODES, K_DEFAULT, VERSION, PatientHistory, Scaler,
                       state_at, to_pgvector)

OUTCOMES = {  # clave de la respuesta: (columna del evento, columna de días)
    "cvd": ("cvd", "days_to_cvd"),
    "chd": ("any_chd", "days_to_any_chd"),
    "stroke": ("stroke", "days_to_stroke"),
    "death": ("death", "days_to_death"),
}
DAYS_PER_YEAR = 365.25


class KnnNotReady(Exception):
    pass


class NotEnoughTests(Exception):
    pass


def load_histories(conn: Connection, patient_ids: list[int] | None = None) -> dict[int, PatientHistory]:
    where, params = ("WHERE patient_id = ANY(%s)", [patient_ids]) if patient_ids is not None else ("", [])
    histories = {r["patient_id"]: PatientHistory(r["patient_id"], r["sex"])
                 for r in conn.execute(f"SELECT patient_id, sex FROM patient {where}", params)}
    for r in conn.execute(f"""
            SELECT patient_id, exam_time, period, days_since_baseline, age_years, current_smoker,
                   cigs_per_day, bp_meds, diabetes, prev_chd, prev_stroke, prev_hypertension
            FROM exam {where} ORDER BY patient_id, exam_time""", params):
        histories[r["patient_id"]].exams.append(r)
    m_where = "AND patient_id = ANY(%s)" if patient_ids is not None else ""
    series: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in conn.execute(f"""
            SELECT patient_id, indicator_code, measured_at, value FROM measurement
            WHERE indicator_code = ANY(%s) {m_where}
            ORDER BY patient_id, indicator_code, measured_at""", [INDICATOR_CODES, *params]):
        series[r["patient_id"]][r["indicator_code"]].append((r["measured_at"], r["value"]))
    for pid, s in series.items():
        if pid in histories:
            histories[pid].series = dict(s)
    return histories


def build_index(conn: Connection) -> dict:
    """(Re)construye el índice: escalador sobre todos los exámenes y un vector por examen."""
    start = time.perf_counter()
    histories = load_histories(conn)
    states = [(h.patient_id, e["exam_time"], state_at(h, e["exam_time"]))
              for h in histories.values() for e in h.exams]
    scaler = Scaler.fit([s for _, _, s in states])
    rows = [(pid, t, VERSION, to_pgvector(scaler.vector(s))) for pid, t, s in states]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM exam_embedding WHERE embedding_version = %s", [VERSION])
        with cur.copy("COPY exam_embedding (patient_id, exam_time, embedding_version, embedding) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
        cur.execute("""
            INSERT INTO embedding_model (version, dimensions, features, exams) VALUES (%s, %s, %s, %s)
            ON CONFLICT (version) DO UPDATE
            SET dimensions = EXCLUDED.dimensions, features = EXCLUDED.features,
                exams = EXCLUDED.exams, created_at = now()
        """, [VERSION, DIMENSIONS, json.dumps(scaler.to_json()), len(rows)])
    return {"version": VERSION, "exams": len(rows), "seconds": round(time.perf_counter() - start, 1)}


_scalers: dict[tuple[str, datetime], Scaler] = {}


def _scaler(conn: Connection) -> Scaler:
    row = conn.execute("SELECT features, created_at FROM embedding_model WHERE version = %s", [VERSION]).fetchone()
    if row is None:
        raise KnnNotReady("El índice KNN no está construido: ejecuta python -m app.jobs.build_knn_index")
    key = (VERSION, row["created_at"])
    if key not in _scalers:
        try:
            _scalers[key] = Scaler.from_json(row["features"])
        except ValueError as exc:
            raise KnnNotReady(str(exc)) from exc
    return _scalers[key]


def _outcome(outcome: dict, days_since_baseline: int) -> dict:
    """Qué le pasó al vecino DESPUÉS del examen comparado."""
    out = {}
    for key, (flag, days) in OUTCOMES.items():
        delta = outcome[days] - days_since_baseline
        if outcome[flag] and delta < 0:
            out[key] = {"status": "before"}                          # ya lo había tenido
        elif outcome[flag]:
            out[key] = {"status": "event", "years": round(delta / DAYS_PER_YEAR, 1)}
        else:
            out[key] = {"status": "none", "years": round(delta / DAYS_PER_YEAR, 1)}
    out["followupYears"] = round(max(outcome["days_to_death"] - days_since_baseline, 0) / DAYS_PER_YEAR, 1)
    return out


def _values(raw: dict) -> dict:
    return {f.key: (None if raw[f.key] is None else round(raw[f.key], max(f.decimals, 1) + 1)) for f in FEATURES}


def find_similar(conn: Connection, patient_id: int, *, include_latest: bool, k: int = K_DEFAULT) -> dict:
    scaler = _scaler(conn)
    history = load_histories(conn, [patient_id])[patient_id]
    times = history.test_times()
    if not include_latest and len(times) < 2:
        raise NotEnoughTests("El paciente solo tiene una prueba: no hay estado anterior a la última")
    t = times[-1] if include_latest else times[-2]
    raw = state_at(history, t)
    if raw is None:
        raise NotEnoughTests("No hay ningún examen anterior a esa prueba")
    z_patient = scaler.z(raw)

    # HNSW devuelve exámenes; se queda el más cercano de cada paciente hasta tener k.
    with conn.transaction():
        conn.execute("SET LOCAL hnsw.ef_search = 200")
        hits = conn.execute("""
            SELECT patient_id, exam_time, embedding <-> %(v)s::vector AS distance
            FROM exam_embedding
            WHERE embedding_version = %(ver)s AND patient_id <> %(pid)s
            ORDER BY embedding <-> %(v)s::vector
            LIMIT 100
        """, {"v": to_pgvector(scaler.vector(raw)), "ver": VERSION, "pid": patient_id}).fetchall()
    best: dict[int, dict] = {}
    for h in hits:
        best.setdefault(h["patient_id"], h)
        if len(best) == k:
            break

    ids = list(best)
    neighbor_histories = load_histories(conn, ids)
    outcomes = {r["patient_id"]: r for r in conn.execute(
        "SELECT * FROM patient_outcome WHERE patient_id = ANY(%s)", [ids])}
    neighbors = []
    for rank, pid in enumerate(ids, start=1):
        hit, h = best[pid], neighbor_histories[pid]
        exam = next(e for e in h.exams if e["exam_time"] == hit["exam_time"])
        n_raw = state_at(h, hit["exam_time"])
        z_n = scaler.z(n_raw)
        neighbors.append({
            "rank": rank,
            "label": f"Caso {rank}",   # anónimo: son otros pacientes
            "distance": round(hit["distance"], 3),
            "similarity": round(100 / (1 + hit["distance"]), 1),
            "exam": {"period": exam["period"], "date": iso(exam["exam_time"])},
            "values": _values(n_raw),
            # |diferencia| en desviaciones estándar respecto al paciente estudiado (sin ponderar)
            "differences": {f.key: (None if raw[f.key] is None or n_raw[f.key] is None
                                    else round(abs(zn - zp), 2))
                            for f, zn, zp in zip(FEATURES, z_n, z_patient)},
            "outcome": _outcome(outcomes[pid], exam["days_since_baseline"]) if pid in outcomes else None,
        })

    with_outcome = [n["outcome"] for n in neighbors if n["outcome"]]
    return {
        "mode": "with_latest" if include_latest else "without_latest",
        "version": VERSION,
        "k": k,
        "referenceTime": iso(t),
        "latestTestTime": iso(times[-1]),
        "features": [{"key": f.key, "label": f.label, "group": f.group, "weight": f.weight,
                      "unit": f.unit, "decimals": f.decimals, "kind": f.kind} for f in FEATURES],
        "patient": {"values": _values(raw)},
        "neighbors": neighbors,
        "summary": {
            "cvdEvents": sum(o["cvd"]["status"] == "event" for o in with_outcome),
            "deaths": sum(o["death"]["status"] == "event" for o in with_outcome),
            "withOutcome": len(with_outcome),
        },
    }
