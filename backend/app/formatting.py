"""Conversión de valores de la base de datos al formato que espera el frontend."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

SEX_LABELS = {"M": "Hombre", "F": "Mujer"}
RISK_LEVELS = ("high", "medium", "low")


def iso(value: datetime | date | None) -> str | None:
    """Fecha ISO: "YYYY-MM-DD" si es medianoche UTC (exámenes de raw.csv), instante completo si no."""
    if value is None:
        return None
    if isinstance(value, datetime):
        utc = value.astimezone(timezone.utc)
        if utc.time() == time(0, 0):
            return utc.date().isoformat()
        return utc.isoformat().replace("+00:00", "Z")
    return value.isoformat()


def risk_percent(probability: float | None) -> float | None:
    """El frontend trabaja en porcentaje (32.4); la base de datos guarda probabilidad (0.324)."""
    return None if probability is None else round(probability * 100, 1)


def risk_level(percent: float | None) -> str | None:
    """Mismos umbrales que src/domain/risk.js: alto >= 20 %, medio 10-20 %, bajo < 10 %."""
    if percent is None:
        return None
    return "high" if percent >= 20 else "medium" if percent >= 10 else "low"


def initials(first: str | None, last: str | None) -> str:
    return ((first or "?")[:1] + (last or "?")[:1]).upper()


def normalize_text(value: str) -> str:
    """Minúsculas sin tildes, como normalize() en src/utils/text.js."""
    import unicodedata
    decomposed = unicodedata.normalize("NFD", value.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
