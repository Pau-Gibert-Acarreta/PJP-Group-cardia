"""Motor de reglas de hallazgos (lógica pura, sin base de datos).

Misma semántica que src/domain/findings.js y src/domain/measurements.js:

- Cada regla activa compara las dos últimas mediciones válidas de su campo.
- Se descartan valores no finitos y mediciones con una unidad distinta de la
  configurada; para un mismo instante se conserva la última recibida.
- Métricas: current, previous, delta (actual - anterior) y percent_change
  ((actual - anterior) / |anterior| * 100, sin evaluar si anterior = 0).
- Todas las condiciones deben cumplirse (AND) y, si existe maxIntervalDays,
  las dos mediciones no pueden estar más separadas que eso.
"""
from __future__ import annotations

import math
import operator
from dataclasses import dataclass
from datetime import datetime

OPERATORS = {
    "gt": operator.gt, "gte": operator.ge,
    "lt": operator.lt, "lte": operator.le, "eq": operator.eq,
}


@dataclass(frozen=True)
class Point:
    value: float
    at: datetime
    unit: str | None = None


@dataclass(frozen=True)
class Summary:
    field: str
    series: list[Point]
    latest: Point | None
    previous: Point | None
    delta: float
    percent_change: float | None


@dataclass(frozen=True)
class Finding:
    rule: dict
    summary: Summary
    interval_days: float


def _precise(value: float) -> float:
    # Igual que Number(value.toPrecision(12)) en JS: evita 0.30000000000000004.
    return float(f"{value:.12g}")


def get_series(points: list[Point], expected_unit: str | None = None) -> list[Point]:
    unique: dict[datetime, Point] = {}
    for p in points:
        if not isinstance(p.value, (int, float)) or not math.isfinite(p.value):
            continue
        if expected_unit and p.unit and p.unit != expected_unit:
            continue
        unique[p.at] = p
    return sorted(unique.values(), key=lambda p: p.at)


def summarize(field: str, points: list[Point], expected_unit: str | None = None) -> Summary:
    series = get_series(points, expected_unit)
    latest = series[-1] if series else None
    previous = series[-2] if len(series) > 1 else None
    delta = _precise(latest.value - previous.value) if latest and previous else 0.0
    pct = (_precise((latest.value - previous.value) / abs(previous.value) * 100)
           if latest and previous and previous.value != 0 else None)
    return Summary(field, series, latest, previous, delta, pct)


def evaluate(measurements: dict[str, list[Point]], indicator_by_field: dict[str, dict],
             rules: list[dict]) -> list[Finding]:
    """Devuelve los hallazgos que se cumplen, en el orden de las reglas."""
    findings: list[Finding] = []
    summaries: dict[str, Summary] = {}
    for rule in rules:
        if rule.get("enabled") is False:
            continue
        definition = indicator_by_field.get(rule["field"])
        if definition is None:
            continue
        field = rule["field"]
        if field not in summaries:
            summaries[field] = summarize(field, measurements.get(field, []), definition.get("unit"))
        s = summaries[field]
        if s.latest is None or s.previous is None:
            continue
        interval_days = (s.latest.at - s.previous.at).total_seconds() / 86400
        max_days = rule.get("maxIntervalDays")
        if max_days is not None and interval_days > max_days:
            continue
        values = {"current": s.latest.value, "previous": s.previous.value,
                  "delta": s.delta, "percent_change": s.percent_change}
        if all(
            values[c["metric"]] is not None and math.isfinite(values[c["metric"]])
            and c["operator"] in OPERATORS and OPERATORS[c["operator"]](values[c["metric"]], c["value"])
            for c in rule["conditions"]
        ):
            findings.append(Finding(rule, s, interval_days))
    return findings
