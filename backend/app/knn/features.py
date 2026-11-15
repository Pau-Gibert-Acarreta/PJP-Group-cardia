"""Vector de un "caso": el estado clínico de un paciente en un instante t.

Un caso combina tres cosas, todas medidas como mucho en t:
- Contexto: edad, sexo, tabaco, diabetes, tratamiento y antecedentes (último examen <= t).
- Valores: el último valor de cada indicador <= t.
- Tendencias: cambio por año entre ese último valor y el anterior del mismo indicador.

Cada variable se estandariza (z-score con la media y la desviación del índice)
y se multiplica por sqrt(peso). Así la distancia L2 de pgvector es la distancia
euclídea ponderada. Un valor ausente queda en z = 0 (la media): no acerca ni aleja.

Pesos: mayores en los predictores clásicos de riesgo cardiovascular (edad, sexo,
PA sistólica y su tendencia, tabaco, diabetes, colesterol, cardiopatía previa;
ecuaciones de Framingham, D'Agostino 2008, y SCORE2, 2021). HDL pesa poco porque
en el estudio solo se midió en el tercer examen; casi todos los estados lo tienen imputado.

Solo se usan variables del dataset original de Framingham. HbA1c, creatinina, eGFR y
ACR se excluyen porque en esta base de datos son sintéticas (db/004_synthetic_fill.sql).
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime

VERSION = "knn-v1"
K_DEFAULT = 7


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    group: str            # context | value | trend
    weight: float
    unit: str = ""
    decimals: int = 0
    kind: str = "number"  # number | bool | sex
    source: str | None = None  # código de indicador (valores y tendencias)


FEATURES: list[Feature] = [
    # Contexto
    Feature("age_years", "Edad", "context", 3.0, "años", 0),
    Feature("sex", "Sexo", "context", 2.0, kind="sex"),
    Feature("current_smoker", "Fumador", "context", 2.0, kind="bool"),
    Feature("cigs_per_day", "Cigarrillos/día", "context", 0.5, "", 0),
    Feature("diabetes", "Diabetes", "context", 2.0, kind="bool"),
    Feature("bp_meds", "Tratamiento antihipertensivo", "context", 1.5, kind="bool"),
    Feature("prev_hypertension", "Hipertensión previa", "context", 1.5, kind="bool"),
    Feature("prev_chd", "Cardiopatía coronaria previa", "context", 2.0, kind="bool"),
    Feature("prev_stroke", "Ictus previo", "context", 1.5, kind="bool"),
    # Valores en t
    Feature("bmi", "IMC", "value", 1.0, "kg/m²", 1, source="bmi"),
    Feature("systolic", "PA sistólica", "value", 2.5, "mmHg", 0, source="systolic"),
    Feature("diastolic", "PA diastólica", "value", 1.0, "mmHg", 0, source="diastolic"),
    Feature("heart_rate", "Frecuencia cardíaca", "value", 0.5, "lpm", 0, source="heart_rate"),
    Feature("total_cholesterol", "Colesterol total", "value", 1.5, "mg/dL", 0, source="total_cholesterol"),
    Feature("hdl_cholesterol", "Colesterol HDL", "value", 0.75, "mg/dL", 0, source="hdl_cholesterol"),
    Feature("glucose", "Glucosa", "value", 1.0, "mg/dL", 0, source="glucose"),
    # Tendencias (cambio por año respecto a la medición anterior)
    Feature("systolic_trend", "PA sistólica", "trend", 1.5, "mmHg/año", 1, source="systolic"),
    Feature("total_cholesterol_trend", "Colesterol total", "trend", 1.0, "mg/dL/año", 1, source="total_cholesterol"),
    Feature("bmi_trend", "IMC", "trend", 0.75, "kg/m²/año", 2, source="bmi"),
    Feature("glucose_trend", "Glucosa", "trend", 0.75, "mg/dL/año", 1, source="glucose"),
]
DIMENSIONS = len(FEATURES)
INDICATOR_CODES = sorted({f.source for f in FEATURES if f.source})
assert DIMENSIONS == 20, "Cambiar el número de variables exige cambiar vector(20) en db/005_knn.sql"


@dataclass
class PatientHistory:
    """Todo lo necesario para calcular el estado de un paciente en cualquier instante."""
    patient_id: int
    sex: str
    exams: list[dict] = field(default_factory=list)                         # ordenados por exam_time
    series: dict[str, list[tuple[datetime, float]]] = field(default_factory=dict)  # ordenadas por tiempo

    def test_times(self) -> list[datetime]:
        """Instantes con alguna prueba (examen o medición), sin repetir, en orden."""
        times = {e["exam_time"] for e in self.exams}
        for points in self.series.values():
            times.update(t for t, _ in points)
        return sorted(times)


def _last_two(points: list[tuple[datetime, float]], t: datetime):
    i = bisect_right([p[0] for p in points], t)
    last = points[i - 1] if i >= 1 else None
    prev = points[i - 2] if i >= 2 else None
    return last, prev


def state_at(history: PatientHistory, t: datetime) -> dict[str, float | None] | None:
    """Variables en crudo del caso en el instante t (None si aún no había ningún examen)."""
    exam = None
    for e in history.exams:
        if e["exam_time"] <= t:
            exam = e
    if exam is None:
        return None
    years_since_exam = (t - exam["exam_time"]).total_seconds() / (365.25 * 86400)
    raw: dict[str, float | None] = {
        "age_years": exam["age_years"] + years_since_exam,
        "sex": 1.0 if history.sex == "M" else 0.0,
        "current_smoker": float(exam["current_smoker"]),
        "cigs_per_day": float(exam["cigs_per_day"]) if exam["cigs_per_day"] is not None else None,
        "diabetes": float(exam["diabetes"]),
        "bp_meds": float(exam["bp_meds"]) if exam["bp_meds"] is not None else None,
        "prev_hypertension": float(exam["prev_hypertension"]),
        "prev_chd": float(exam["prev_chd"]),
        "prev_stroke": float(exam["prev_stroke"]),
    }
    for f in FEATURES:
        if f.group == "context":
            continue
        last, prev = _last_two(history.series.get(f.source, []), t)
        if f.group == "value":
            raw[f.key] = last[1] if last else None
        else:
            years = (last[0] - prev[0]).total_seconds() / (365.25 * 86400) if last and prev else 0
            raw[f.key] = (last[1] - prev[1]) / years if years > 0 else None
    return raw


@dataclass(frozen=True)
class Scaler:
    means: list[float]
    stds: list[float]

    @classmethod
    def fit(cls, states: list[dict]) -> "Scaler":
        means, stds = [], []
        for f in FEATURES:
            values = [s[f.key] for s in states if s[f.key] is not None]
            mean = sum(values) / len(values) if values else 0.0
            var = sum((v - mean) ** 2 for v in values) / len(values) if values else 0.0
            means.append(mean)
            stds.append(math.sqrt(var) or 1.0)
        return cls(means, stds)

    def z(self, raw: dict) -> list[float]:
        """z-score por variable; 0 si falta."""
        return [0.0 if raw[f.key] is None else (raw[f.key] - m) / s
                for f, m, s in zip(FEATURES, self.means, self.stds)]

    def vector(self, raw: dict) -> list[float]:
        return [z * math.sqrt(f.weight) for z, f in zip(self.z(raw), FEATURES)]

    def to_json(self) -> list[dict]:
        return [{"key": f.key, "weight": f.weight, "mean": m, "std": s}
                for f, m, s in zip(FEATURES, self.means, self.stds)]

    @classmethod
    def from_json(cls, data: list[dict]) -> "Scaler":
        if [(d["key"], d["weight"]) for d in data] != [(f.key, f.weight) for f in FEATURES]:
            raise ValueError("El índice KNN se construyó con otras variables o pesos: vuelve a construirlo")
        return cls([d["mean"] for d in data], [d["std"] for d in data])


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"
