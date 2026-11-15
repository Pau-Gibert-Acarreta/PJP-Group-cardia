"""Explicación local (SHAP) de cada predicción.

Valores SHAP exactos (intervencionales) sobre las 6 variables de entrada del modelo:
con 6 variables se pueden evaluar las 2^6 = 64 coaliciones, así que no hace falta
aproximar (equivale a KernelExplainer con todas las coaliciones). Se explica el
log-riesgo relativo del Cox, que es aditivo: base + suma(SHAP) = log-riesgo del paciente.
El valor base es el log-riesgo medio de una muestra de entrenamiento (background).
"""
from __future__ import annotations

from itertools import combinations
from math import factorial

import numpy as np
import pandas as pd

LABELS = {
    "age": ("Edad", "años"),
    "sex": ("Sexo", ""),
    "current_smoker": ("Tabaquismo", ""),
    "systolic_bp": ("Presión arterial sistólica", "mmHg"),
    "total_cholesterol": ("Colesterol total", "mg/dL"),
    "hdl_cholesterol": ("Colesterol HDL", "mg/dL"),
}
MGDL_PER_MMOLL = 38.67


def shap_values(predict, x: pd.DataFrame, background: pd.DataFrame) -> tuple[float, np.ndarray]:
    """(valor base, SHAP de cada columna) para una fila `x` (DataFrame de 1 fila)."""
    cols = list(x.columns)
    n = len(cols)
    coalitions = [frozenset(c) for k in range(n + 1) for c in combinations(range(n), k)]
    # Una sola llamada al modelo con todas las coaliciones x background.
    blocks = []
    for coalition in coalitions:
        block = background.copy()
        for i in coalition:
            block[cols[i]] = x.iloc[0, i]
        blocks.append(block)
    values = np.asarray(predict(pd.concat(blocks, ignore_index=True)), dtype=float)
    value = {c: values[j * len(background):(j + 1) * len(background)].mean() for j, c in enumerate(coalitions)}
    phi = np.zeros(n)
    for i in range(n):
        for coalition in coalitions:
            if i in coalition:
                continue
            weight = factorial(len(coalition)) * factorial(n - len(coalition) - 1) / factorial(n)
            phi[i] += weight * (value[coalition | {i}] - value[coalition])
    return float(value[frozenset()]), phi


def describe(feature: str, value) -> tuple[str, object, str]:
    """Etiqueta, valor en unidades clínicas de la app y unidad (colesterol en mg/dL)."""
    label, unit = LABELS[feature]
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return label, None, unit
    if feature == "sex":
        return label, "Hombre" if value == "male" else "Mujer", ""
    if feature == "current_smoker":
        return label, "Fumador" if float(value) >= 0.5 else "No fumador", ""
    if feature in ("total_cholesterol", "hdl_cholesterol"):
        return label, round(float(value) * MGDL_PER_MMOLL), unit
    return label, round(float(value)), unit


def top_k(x: pd.DataFrame, phi: np.ndarray, k: int = 6) -> list[dict]:
    """Variables ordenadas por |SHAP|, con el formato que guarda risk_prediction.shap_top_k."""
    order = np.argsort(-np.abs(phi))[:k]
    out = []
    for i in order:
        feature = x.columns[i]
        label, value, unit = describe(feature, x.iloc[0, i])
        out.append({"feature": feature, "label": label, "value": value, "unit": unit,
                    "contribution": round(float(phi[i]), 6)})
    return out
