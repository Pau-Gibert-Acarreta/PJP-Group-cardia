"""Lee una analítica en PDF (formato de app/jobs/generate_lab_reports.py).

Los PDF son digitales: basta con extraer el texto (no hace falta OCR). pypdf devuelve
cada celda en su propia línea, en orden: nombre de la prueba, nota opcional,
resultado, unidades y valores de referencia.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from pypdf import PdfReader

# Prueba del informe -> (indicator.code, decimales con que se imprime)
TESTS = {
    "Glucosa": ("glucose", 0),
    "Hemoglobina glicada (HbA1c)": ("hba1c", 1),
    "Creatinina": ("serum_creatinine", 2),          # línea exacta: no confundir con "Creatinina en orina"
    "Filtrado glomerular estimado": ("egfr", 0),
    "Colesterol total": ("total_cholesterol", 0),
    "Colesterol HDL": ("hdl_cholesterol", 0),
    "Colesterol LDL": ("ldl", 0),
    "Cociente albúmina/creatinina": ("acr", 1),
}
DECIMALS = {code: d for code, d in TESTS.values()}
NOTES = {"Suero · determinación casual", "CKD-EPI 2021"}
NUMBER = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d+))?")


class LabReportError(ValueError):
    pass


@dataclass
class LabReport:
    request: str                  # Nº de petición "RANDID-PERIODO"
    patient_id: int
    period: int
    cip: str
    extraction_date: date
    values: dict[str, float | None] = field(default_factory=dict)   # indicator.code -> valor (None = no determinado)


def _number(text: str) -> float | None:
    m = NUMBER.match(text.strip())
    if not m:
        return None
    return float(m.group(1).replace(".", "") + ("." + m.group(2) if m.group(2) else ""))


def _after(lines: list[str], label: str) -> str:
    """Valor que sigue a una etiqueta de los datos del paciente ("CIP:" -> "SYN0002448")."""
    for i, line in enumerate(lines):
        if line == label and i + 1 < len(lines):
            return lines[i + 1]
    raise LabReportError(f"No se encuentra «{label}» en el informe")


def parse_text(text: str) -> LabReport:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    request_line = next((line for line in lines if line.startswith("Nº de petición:")), None)
    date_line = next((line for line in lines if line.startswith("Fecha de extracción:")), None)
    if not request_line or not date_line:
        raise LabReportError("No parece una analítica: falta el nº de petición o la fecha de extracción")
    request = request_line.split(":", 1)[1].strip()
    m = re.fullmatch(r"(\d+)-(\d+)", request)
    if not m:
        raise LabReportError(f"Nº de petición inesperado: {request}")
    extraction = datetime.strptime(date_line.split(":", 1)[1].strip(), "%d/%m/%Y").date()

    values: dict[str, float | None] = {}
    for i, line in enumerate(lines):
        if line not in TESTS or TESTS[line][0] in values:
            continue
        j = i + 1
        if j < len(lines) and lines[j] in NOTES:
            j += 1
        if j >= len(lines):
            continue
        result = lines[j]
        values[TESTS[line][0]] = None if result.startswith("No determinado") else _number(result)
    missing = [label for label, (code, _) in TESTS.items() if code not in values]
    if missing:
        raise LabReportError(f"Faltan pruebas en el informe: {', '.join(missing)}")
    return LabReport(request, int(m.group(1)), int(m.group(2)), _after(lines, "CIP:"), extraction, values)


def parse_pdf(data: bytes) -> LabReport:
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise LabReportError(f"PDF ilegible: {exc}") from exc
    return parse_text(text)


def matches(code: str, printed: float | None, stored: float | None) -> bool:
    """¿El valor impreso (redondeado) corresponde al guardado en la base de datos?"""
    if printed is None or stored is None:
        return printed is None and stored is None
    return abs(round(stored, DECIMALS[code]) - printed) < 10 ** -DECIMALS[code] / 2 + 1e-9
