"""Datos para el modelo de riesgo, leídos de la base de datos.

`load_raw()` devuelve, desde PostgreSQL, una tabla con exactamente las mismas columnas,
códigos y unidades que data/raw.csv (RANDID, SEX 1/2, TOTCHOL en mg/dL, TIME en días...).
A partir de ahí, todo es la misma lógica que usaba el equipo con el CSV/parquet:

- Notebook 01 (bronze -> silver -> gold): cohorte de la visita 3, etiqueta target_broad_10y
  y partición train/test 80/20 estratificada con semilla 42.
- Búsqueda de modelos (experiments/coxph): entrena con las visitas 1, 2 y 3 de los pacientes
  que no están en test, 40-69 años, sin diabetes ni cardiopatía o ictus previos, con
  y = [evento amplio a 10 años, días hasta el evento o la censura/muerte, truncado a 10 años].

Comprobado: el pipeline reentrenado con estos datos reproduce los coeficientes del modelo
congelado (|diferencia| < 1e-10) y sus 454 predicciones de test.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

HORIZON_DAYS = 10 * 365.25
CHOLESTEROL_MGDL_PER_MMOLL = 38.67
SPLIT_SEED = 42
MODEL_FEATURES = ["age", "sex", "current_smoker", "systolic_bp", "total_cholesterol", "hdl_cholesterol"]

# Mismo mapeo que el notebook 01
BASE_MAP = {'AGE': 'age', 'SEX': 'sex', 'CURSMOKE': 'current_smoker',
            'SYSBP': 'systolic_bp', 'TOTCHOL': 'total_cholesterol', 'HDLC': 'hdl_cholesterol'}
PLUS_MAP = {'BMI': 'bmi', 'GLUCOSE': 'glucose', 'DIABP': 'diastolic_bp', 'BPMEDS': 'bp_medication',
            'CIGPDAY': 'cigarettes_per_day', 'HEARTRTE': 'heart_rate', 'LDLC': 'ldl_cholesterol',
            'educ': 'education', 'PREVHYP': 'previous_hypertension'}
META_MAP = {'RANDID': 'patient_id', 'PERIOD': 'exam_period', 'TIME': 'days_since_first_exam',
            'DIABETES': 'diabetes', 'PREVCHD': 'previous_chd', 'PREVSTRK': 'previous_stroke',
            'PREVMI': 'previous_mi', 'PREVAP': 'previous_angina'}
EVENT_TIMES = {'HOSPMI': 'TIMEMI', 'STROKE': 'TIMESTRK', 'MI_FCHD': 'TIMEMIFC',
               'ANGINA': 'TIMEAP', 'ANYCHD': 'TIMECHD', 'CVD': 'TIMECVD'}
RAW_COLUMNS = ["RANDID", "SEX", "TOTCHOL", "AGE", "SYSBP", "DIABP", "CURSMOKE", "CIGPDAY", "BMI", "DIABETES",
               "BPMEDS", "HEARTRTE", "GLUCOSE", "educ", "PREVCHD", "PREVAP", "PREVMI", "PREVSTRK", "PREVHYP",
               "TIME", "PERIOD", "HDLC", "LDLC", "DEATH", "ANGINA", "HOSPMI", "MI_FCHD", "ANYCHD", "STROKE",
               "CVD", "HYPERTEN", "TIMEAP", "TIMEMI", "TIMEMIFC", "TIMECHD", "TIMESTRK", "TIMECVD", "TIMEDTH",
               "TIMEHYP"]


def database_url() -> str:
    return os.environ.get("CARDIA_DATABASE_URL", "postgresql://postgres:cardia@localhost:5432/cardia")


_RAW_SQL = """
SELECT e.patient_id AS "RANDID",
       CASE p.sex WHEN 'M' THEN 1 ELSE 2 END AS "SEX",
       max(m.value) FILTER (WHERE m.indicator_code = 'total_cholesterol') AS "TOTCHOL",
       e.age_years AS "AGE",
       max(m.value) FILTER (WHERE m.indicator_code = 'systolic') AS "SYSBP",
       max(m.value) FILTER (WHERE m.indicator_code = 'diastolic') AS "DIABP",
       e.current_smoker::int AS "CURSMOKE", e.cigs_per_day AS "CIGPDAY",
       max(m.value) FILTER (WHERE m.indicator_code = 'bmi') AS "BMI",
       e.diabetes::int AS "DIABETES", e.bp_meds::int AS "BPMEDS",
       max(m.value) FILTER (WHERE m.indicator_code = 'heart_rate') AS "HEARTRTE",
       max(m.value) FILTER (WHERE m.indicator_code = 'glucose') AS "GLUCOSE",
       p.education_level AS "educ",
       e.prev_chd::int AS "PREVCHD", e.prev_angina::int AS "PREVAP", e.prev_mi::int AS "PREVMI",
       e.prev_stroke::int AS "PREVSTRK", e.prev_hypertension::int AS "PREVHYP",
       e.days_since_baseline AS "TIME", e.period AS "PERIOD",
       max(m.value) FILTER (WHERE m.indicator_code = 'hdl_cholesterol') AS "HDLC",
       max(m.value) FILTER (WHERE m.indicator_code = 'ldl') AS "LDLC",
       o.death::int AS "DEATH", o.angina::int AS "ANGINA", o.hosp_mi::int AS "HOSPMI", o.mi_fchd::int AS "MI_FCHD",
       o.any_chd::int AS "ANYCHD", o.stroke::int AS "STROKE", o.cvd::int AS "CVD", o.hypertension::int AS "HYPERTEN",
       o.days_to_angina AS "TIMEAP", o.days_to_hosp_mi AS "TIMEMI", o.days_to_mi_fchd AS "TIMEMIFC",
       o.days_to_any_chd AS "TIMECHD", o.days_to_stroke AS "TIMESTRK", o.days_to_cvd AS "TIMECVD",
       o.days_to_death AS "TIMEDTH", o.days_to_hypertension AS "TIMEHYP"
FROM cardia.exam e
JOIN cardia.patient p USING (patient_id)
JOIN cardia.patient_outcome o USING (patient_id)
LEFT JOIN cardia.measurement m ON m.patient_id = e.patient_id AND m.measured_at = e.exam_time
WHERE e.period IS NOT NULL
GROUP BY e.patient_id, p.sex, e.age_years, e.current_smoker, e.cigs_per_day, e.diabetes, e.bp_meds,
         p.education_level, e.prev_chd, e.prev_angina, e.prev_mi, e.prev_stroke, e.prev_hypertension,
         e.days_since_baseline, e.period, o.patient_id
ORDER BY e.patient_id, e.period
"""


def load_raw(conn=None) -> pd.DataFrame:
    """La tabla de raw.csv, reconstruida desde la base de datos (una fila por paciente y visita)."""
    import psycopg
    close = conn is None
    conn = conn or psycopg.connect(database_url())
    try:
        with conn.cursor() as cur:
            cur.execute(_RAW_SQL)
            rows = cur.fetchall()
    finally:
        if close:
            conn.close()
    df = pd.DataFrame(rows, columns=RAW_COLUMNS)
    return df.apply(pd.to_numeric, errors="raise").astype(float)


# ---------------------------------------------------------------- etiquetas (igual que el notebook 01)

def label_event_10y(frame, event_col, time_col, horizon=HORIZON_DAYS):
    """Etiqueta binaria nullable y motivo; tiempos originales desde visita 1."""
    t0 = frame['days_since_first_exam']
    event = frame[event_col]
    delta = frame[time_col] - t0
    death = frame['DEATH']
    death_delta = frame['TIMEDTH'] - t0
    died = death.eq(1) & death_delta.gt(0)
    invalid = (
        ~event.isin([0, 1]) | delta.isna() | delta.lt(0)
        | (event.eq(1) & delta.le(0))
        | (death.eq(1) & (death_delta.isna() | death_delta.le(0)))
        | (event.eq(1) & died & delta.gt(death_delta))
    )
    positive = ~invalid & event.eq(1) & delta.gt(0) & delta.le(horizon)
    full_window = ~invalid & delta.ge(horizon)
    followed_until_death = ~invalid & died & death_delta.le(horizon) & delta.ge(death_delta)
    negative = ~positive & ~invalid & (full_window | followed_until_death)
    label = pd.Series(pd.NA, index=frame.index, dtype='Int64')
    label.loc[negative] = 0
    label.loc[positive] = 1
    return label


def nullable_event_or(labels):
    result = pd.Series(pd.NA, index=labels.index, dtype='Int64')
    result.loc[labels.eq(0).all(axis=1) & labels.notna().all(axis=1)] = 0
    result.loc[labels.eq(1).any(axis=1)] = 1
    return result


def _bronze(raw: pd.DataFrame) -> pd.DataFrame:
    return raw.rename(columns={**BASE_MAP, **PLUS_MAP, **META_MAP})


def _eligible(frame: pd.DataFrame) -> pd.Series:
    """Criterios de la cohorte silver (salvo la visita): 40-69 años, sin diabetes, CHD ni ictus previos."""
    return (frame.age.between(40, 69) & frame.diabetes.eq(0)
            & frame.previous_chd.eq(0) & frame.previous_stroke.eq(0))


def _to_model_units(frame: pd.DataFrame) -> pd.DataFrame:
    X = frame[MODEL_FEATURES].copy()
    X["sex"] = X["sex"].map({1: "male", 2: "female"})
    X["total_cholesterol"] = X["total_cholesterol"] / CHOLESTEROL_MGDL_PER_MMOLL
    X["hdl_cholesterol"] = X["hdl_cholesterol"] / CHOLESTEROL_MGDL_PER_MMOLL
    return X


# ---------------------------------------------------------------- cohortes

def silver_cohort(raw: pd.DataFrame) -> pd.DataFrame:
    """Cohorte silver (visita 3) con target_broad_10y, igual que el notebook 01."""
    b = _bronze(raw)
    cohort = b[b.exam_period.eq(3)]
    cohort = cohort[_eligible(cohort)].copy()
    labels = pd.DataFrame({ev + '_10y': label_event_10y(cohort, ev, tc) for ev, tc in EVENT_TIMES.items()})
    cohort["target_broad_10y"] = nullable_event_or(labels)
    return cohort


def train_test_ids(raw: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Partición del notebook 01: etiquetas conocidas, 80/20 estratificada, semilla 42."""
    from sklearn.model_selection import train_test_split
    silver = silver_cohort(raw).set_index("patient_id")
    known = silver[silver.target_broad_10y.notna()]
    train_ids, test_ids = train_test_split(known.index.to_numpy(), test_size=0.20, random_state=SPLIT_SEED,
                                           stratify=known.target_broad_10y.astype("int64").to_numpy())
    return train_ids, test_ids


def training_set(raw: pd.DataFrame, test_ids) -> tuple[pd.DataFrame, np.ndarray]:
    """Datos de entrenamiento de la búsqueda (visits=123, age=40-69): X y y = [evento, tiempo]."""
    b = _bronze(raw)
    d = b[~b.patient_id.isin(set(test_ids))]
    d = d[_eligible(d)].copy()
    t0 = d.days_since_first_exam
    deltas = pd.DataFrame({ev: d[tc] - t0 for ev, tc in EVENT_TIMES.items()})
    flags = pd.DataFrame({ev: d[ev] for ev in EVENT_TIMES})
    positive = (flags == 1) & (deltas > 0) & (deltas <= HORIZON_DAYS)
    event = positive.any(axis=1)
    death_delta = d.TIMEDTH - t0
    died = d.DEATH.eq(1) & death_delta.gt(0)
    censor = np.minimum(deltas.min(axis=1).clip(upper=HORIZON_DAYS), np.where(died, death_delta, np.inf))
    time = np.minimum(np.where(event, deltas.where(positive).min(axis=1), censor), HORIZON_DAYS)
    keep = time > 0
    y = np.column_stack([event[keep].astype(float), time[keep]])
    return _to_model_units(d[keep]), y


def test_set(raw: pd.DataFrame, test_ids) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Test del notebook (visita 3, sin imputar): X, target_broad_10y y patient_id."""
    silver = silver_cohort(raw).set_index("patient_id").loc[list(test_ids)]
    return _to_model_units(silver.reset_index()), silver.target_broad_10y.astype(int).to_numpy(), silver.index.to_numpy()


# ---------------------------------------------------------------- serving

def features_from_backend(f: dict) -> pd.DataFrame:
    """Variables que envía el Core Backend (risk_service.build_features) -> fila del modelo.

    Mismas unidades que el entrenamiento: sexo male/female y colesterol en mmol/L.
    Un valor ausente se deja como NaN: lo imputa el propio pipeline (mediana + indicador).
    """
    def num(key):
        value = f.get(key)
        return float(value) if isinstance(value, (int, float, bool)) else np.nan

    sex = f.get("sex")
    row = {
        "age": num("age_years"),
        "sex": "male" if sex in ("M", "male", 1) else "female" if sex in ("F", "female", 2) else None,
        "current_smoker": num("current_smoker"),
        "systolic_bp": num("systolic"),
        "total_cholesterol": num("total_cholesterol") / CHOLESTEROL_MGDL_PER_MMOLL,
        "hdl_cholesterol": num("hdl_cholesterol") / CHOLESTEROL_MGDL_PER_MMOLL,
    }
    return pd.DataFrame([row], columns=MODEL_FEATURES)
