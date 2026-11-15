"""Tipos de prueba: qué indicadores agrupa cada una y cómo aparece en la línea temporal.

Una visita del estudio no es un único evento: cada prueba es un evento propio con sus
resultados. Solo la analítica de sangre tiene informe del laboratorio en PDF.
Única definición, usada por el ETL, la ingesta de PDFs, el evento "Nueva prueba" y la API.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestKind:
    key: str            # clinical_event.test_kind
    event_type: str     # clinical_event.event_type
    title: str          # título en la línea temporal
    label: str          # tipo que se muestra bajo el título
    icon: str           # icono del frontend (src/ui/icons.js)
    codes: tuple[str, ...]  # indicator.code, en el orden en que se muestran
    has_report: bool    # si tiene informe PDF del laboratorio


TEST_KINDS: dict[str, TestKind] = {
    "blood": TestKind("blood", "laboratory", "Analítica de sangre", "Analítica", "flask",
                      ("glucose", "total_cholesterol", "hdl_cholesterol", "ldl", "hba1c", "serum_creatinine", "egfr"),
                      has_report=True),
    "vitals": TestKind("vitals", "exploration", "Presión arterial y constantes", "Constantes", "heart",
                       ("systolic", "diastolic", "heart_rate", "bmi"), has_report=False),
    "urine": TestKind("urine", "laboratory", "Prueba de orina", "Orina", "clipboard",
                      ("acr",), has_report=False),
}

KIND_BY_CODE = {code: kind for kind in TEST_KINDS.values() for code in kind.codes}


def kinds_for(codes) -> list[TestKind]:
    """Tipos de prueba presentes en un conjunto de indicadores, en orden estable."""
    present = {KIND_BY_CODE[c].key for c in codes if c in KIND_BY_CODE}
    return [k for k in TEST_KINDS.values() if k.key in present]
