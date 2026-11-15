"""ETL: carga las fuentes de data/sources/ en la base de datos.

Transformaciones (las que antes hacían los scripts SQL db/002 y db/004, ya retirados):

- Fechas: día de estudio (TIME) -> instante absoluto = fecha base + días (medianoche UTC).
- Paciente: sexo 1/2 -> M/F; año de nacimiento = año base - edad en la primera visita.
- Flags 0/1 -> booleanos; vacío -> NULL (solo donde la columna lo admite).
- Mediciones: una fila por valor presente; los ausentes no se guardan.
- Normalización de nombres: código LOINC del laboratorio -> indicator.code, comprobando la unidad.
- Derivadas: eGFR con CKD-EPI 2021 a partir de la creatinina, la edad y el sexo de la visita.
- Línea temporal: un evento por tipo de prueba y día (analítica de sangre, orina, constantes).
- Trazabilidad: un ingestion_batch por fuente; cada fila apunta al lote del que vino.

Cualquier inconsistencia (paciente desconocido, LOINC sin mapear, unidad distinta) aborta la
carga entera: se ejecuta en una sola transacción.
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

from psycopg import Connection

from ..clinical_tests import KIND_BY_CODE, TEST_KINDS
from ..settings import REPO_ROOT
from .sources import rnd

SCHEMA_FILES = [REPO_ROOT / "db" / "001_schema.sql", REPO_ROOT / "db" / "005_knn.sql"]

# Normalización de nombres: LOINC -> indicator.code (y unidad esperada)
LOINC_TO_INDICATOR = {
    "2345-7": ("glucose", "mg/dL"),
    "2093-3": ("total_cholesterol", "mg/dL"),
    "2085-9": ("hdl_cholesterol", "mg/dL"),
    "13457-7": ("ldl", "mg/dL"),
    "4548-4": ("hba1c", "%"),
    "2160-0": ("serum_creatinine", "mg/dL"),
    "9318-7": ("acr", "mg/g"),
}
VITALS = {"systolic_mmhg": "systolic", "diastolic_mmhg": "diastolic",
          "heart_rate_bpm": "heart_rate", "bmi_kg_m2": "bmi"}


class EtlError(ValueError):
    pass


@dataclass
class LoadStats:
    rows: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


def _read(path: Path) -> list[dict]:
    if not path.exists():
        raise EtlError(f"Falta la fuente {path.name} (ejecuta python -m app.jobs.build_sources)")
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(text: str | None) -> float | None:
    text = (text or "").strip()
    return None if text == "" else float(text)


def _flag(text: str | None) -> bool | None:
    value = _num(text)
    return None if value is None else value == 1


def egfr_ckd_epi_2021(creatinine: float, age: float, female: bool) -> float:
    k, a = (0.7, -0.241) if female else (0.9, -0.302)
    r = creatinine / k
    return 142 * min(r, 1) ** a * max(r, 1) ** -1.200 * 0.9938 ** age * (1.012 if female else 1)


def reset_schema(conn: Connection) -> None:
    """Vacía la base de datos: borra el esquema cardia y lo vuelve a crear (001 + 005)."""
    conn.execute("DROP SCHEMA IF EXISTS cardia CASCADE")
    for path in SCHEMA_FILES:
        conn.execute(path.read_text(encoding="utf-8"))
    conn.execute("SET search_path = cardia, public")


def load(conn: Connection, sources: Path, baseline: date) -> LoadStats:
    start = time.perf_counter()
    stats = LoadStats()
    anchor = datetime.combine(baseline, dtime(0), tzinfo=timezone.utc)
    at = lambda day: anchor + timedelta(days=int(day))  # noqa: E731

    def batch(name: str, rows_read: int) -> str:
        return conn.execute("""
            INSERT INTO ingestion_batch (source_kind, source_uri, rows_read) VALUES (%s, %s, %s) RETURNING batch_id
        """, ["timeseries" if name.startswith("data_") else "tabular",
              f"file://data/sources/{name}", rows_read]).fetchone()["batch_id"]

    def close(batch_id, loaded: int):
        conn.execute("UPDATE ingestion_batch SET status = 'succeeded', finished_at = now(), rows_loaded = %s "
                     "WHERE batch_id = %s", [loaded, batch_id])

    if conn.execute("SELECT EXISTS (SELECT 1 FROM patient)").fetchone()["exists"]:
        raise EtlError("La base de datos ya tiene pacientes: usa --reset para vaciarla antes de cargar")

    # ---- Historia clínica: pacientes y visitas
    patients = _read(sources / "ehr_patients.csv")
    visits = _read(sources / "ehr_visits.csv")
    first_age = {}
    for v in sorted(visits, key=lambda v: (v["patient_id"], int(v["visit"]))):
        first_age.setdefault(v["patient_id"], int(v["age"]))
    b = batch("ehr_patients.csv", len(patients))
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO patient (patient_id, sex, education_level, birth_year, baseline_date,
                                 first_name, last_name, cip, phone, email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, [(int(p["patient_id"]), "M" if p["sex"] == "1" else "F", int(_num(p["education"])) if _num(p["education"]) else None,
               baseline.year - first_age[p["patient_id"]], baseline,
               p["first_name"] or None, p["last_name"] or None, p["cip"] or None, p["phone"] or None, p["email"] or None)
              for p in patients])
    close(b, len(patients))
    sex = {int(p["patient_id"]): p["sex"] for p in patients}

    b = batch("ehr_visits.csv", len(visits))
    exam_rows, exam_index = [], {}
    for v in visits:
        pid = int(v["patient_id"])
        if pid not in sex:
            raise EtlError(f"Visita de un paciente desconocido: {pid}")
        t = at(v["study_day"])
        exam_index[(pid, t)] = int(v["age"])
        exam_rows.append((pid, t, int(v["visit"]), int(v["study_day"]), int(v["age"]),
                          _flag(v["cursmoke"]), int(_num(v["cigpday"])) if _num(v["cigpday"]) is not None else None,
                          _flag(v["bpmeds"]), _flag(v["diabetes"]), _flag(v["prevchd"]), _flag(v["prevap"]),
                          _flag(v["prevmi"]), _flag(v["prevstrk"]), _flag(v["prevhyp"]), b))
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO exam (patient_id, exam_time, period, days_since_baseline, age_years, current_smoker,
                              cigs_per_day, bp_meds, diabetes, prev_chd, prev_angina, prev_mi, prev_stroke,
                              prev_hypertension, ingestion_batch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, exam_rows)
    close(b, len(exam_rows))

    # ---- Mediciones: constantes (ancho) y laboratorio (largo, LOINC)
    measurements: list[tuple] = []

    def add(pid: int, day: str, code: str, value: float, source: str, batch_id):
        t = at(day)
        if (pid, t) not in exam_index:
            raise EtlError(f"Medición {code} de {pid} el día {day} sin visita en la historia clínica")
        measurements.append((pid, code, t, value, source, batch_id))

    pressure = _read(sources / "data_pressure.csv")
    b = batch("data_pressure.csv", len(pressure))
    before = len(measurements)
    for r in pressure:
        for column, code in VITALS.items():
            value = _num(r[column])
            if value is not None:
                add(int(r["patient_id"]), r["study_day"], code, value, "exam", b)
    pressure_batch, pressure_loaded = b, len(measurements) - before

    for name in ("data_blood.csv", "data_urine.csv"):
        rows = _read(sources / name)
        b = batch(name, len(rows))
        before = len(measurements)
        for r in rows:
            if r["loinc"] not in LOINC_TO_INDICATOR:
                raise EtlError(f"{name}: código LOINC sin mapear {r['loinc']}")
            code, unit = LOINC_TO_INDICATOR[r["loinc"]]
            if r["unit"] != unit:
                raise EtlError(f"{name}: {r['loinc']} en {r['unit']}, se esperaba {unit}")
            pid = int(r["patient_id"])
            value = float(r["value"])
            add(pid, r["study_day"], code, value, "lab", b)
            if code == "serum_creatinine":   # derivada: eGFR con CKD-EPI 2021
                age = exam_index[(pid, at(r["study_day"]))]
                add(pid, r["study_day"], "egfr", rnd(egfr_ckd_epi_2021(value, age, sex[pid] == "2"), 0), "lab", b)
        close(b, len(measurements) - before)
    close(pressure_batch, pressure_loaded)

    # ---- Línea temporal: un evento por tipo de prueba realizado ese día (no uno por visita)
    performed = sorted({(pid, t, KIND_BY_CODE[code].key) for pid, code, t, *_ in measurements if code in KIND_BY_CODE},
                       key=lambda e: (e[0], e[1], list(TEST_KINDS).index(e[2])))
    events = [(pid, t, TEST_KINDS[k].event_type, TEST_KINDS[k].title, k) for pid, t, k in performed]

    with conn.cursor() as cur:
        cur.executemany("INSERT INTO clinical_event (patient_id, event_time, event_type, title, test_kind) "
                        "VALUES (%s, %s, %s, %s, %s)", events)
        with cur.copy("COPY measurement (patient_id, indicator_code, measured_at, value, source, ingestion_batch_id) "
                      "FROM STDIN") as copy:
            for row in measurements:
                copy.write_row(row)

    # ---- Registro de seguimiento (etiquetas)
    outcomes = _read(sources / "registry_outcomes.csv")
    b = batch("registry_outcomes.csv", len(outcomes))
    flags = ["death", "angina", "hospmi", "mi_fchd", "anychd", "stroke", "cvd", "hyperten"]
    days = ["timedth", "timeap", "timemi", "timemifc", "timechd", "timestrk", "timecvd", "timehyp"]
    with conn.cursor() as cur:
        cur.executemany(f"INSERT INTO patient_outcome VALUES (%s, {', '.join(['%s'] * 16)})",
                        [(int(o["patient_id"]), *[o[f] == "1" for f in flags], *[int(o[d]) for d in days])
                         for o in outcomes])
    close(b, len(outcomes))

    for table in ("patient", "exam", "measurement", "patient_outcome", "clinical_event"):
        stats.rows[table] = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
    stats.seconds = round(time.perf_counter() - start, 1)
    return stats
