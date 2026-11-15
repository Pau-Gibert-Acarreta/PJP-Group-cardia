"""Modelo de riesgo congelado (Champion del registro) y su predicción a 10 años.

El modelo es un Cox de riesgos proporcionales (scikit-survival) con splines sobre las
6 variables de SCORE2. `predict()` del pipeline devuelve el log-riesgo relativo; la
probabilidad de evento a 10 años es 1 - S(10 años | x), con la supervivencia basal
estimada por el propio Cox.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ML_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ML_ROOT / "models"
REGISTRY = MODELS_DIR / "registry.json"

# Los pickles referencian los módulos del equipo (pipeline_lib_pl, surv_models) por nombre.
_SRC = str(ML_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

HORIZON_DAYS = 10 * 365.25


@dataclass(frozen=True)
class LoadedModel:
    name: str
    version: str
    pipeline: object
    metrics: dict
    background: pd.DataFrame      # muestra de entrenamiento para SHAP

    @property
    def cox(self):
        return self.pipeline.named_steps["model"].model_

    def risk_score(self, X: pd.DataFrame) -> np.ndarray:
        """Log-riesgo relativo (lo que optimiza la búsqueda; mayor = más riesgo)."""
        return np.asarray(self.pipeline.predict(X), dtype=float)

    def probability(self, X: pd.DataFrame, horizon_days: float = HORIZON_DAYS) -> np.ndarray:
        """Probabilidad de evento cardiovascular (compuesto amplio) antes de `horizon_days`."""
        Xt = self.pipeline[:-1].transform(X)
        surv = self.cox.predict_survival_function(np.asarray(Xt, dtype=float))
        return np.array([1.0 - float(fn(min(horizon_days, fn.x[-1]))) for fn in surv])


def registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load(version: str | None = None) -> LoadedModel:
    """Carga el Champion (o una versión concreta) tal y como se guardó: pesos congelados."""
    import joblib
    reg = registry()
    version = version or reg["champion"]
    entry = next(m for m in reg["models"] if m["version"] == version)
    try:
        pipeline = joblib.load(MODELS_DIR / entry["file"])
    except (AttributeError, ModuleNotFoundError, ImportError) as exc:
        # El pickle depende de las versiones exactas de scikit-learn/scipy con que se guardó.
        import platform
        import scipy
        import sklearn
        raise RuntimeError(
            f"No se puede cargar {entry['file']}: las librerías no coinciden con las del entrenamiento "
            f"(Python {platform.python_version()}, scikit-learn {sklearn.__version__}, scipy {scipy.__version__}; "
            f"hace falta Python 3.12+, scikit-learn 1.9.1 y scipy 1.18). Ejecuta 'uv sync' en ml/ "
            f"o vuelve a lanzar setup.cmd / setup.sh. Detalle: {exc}") from exc
    background = pd.read_parquet(MODELS_DIR / entry["background"]) if entry.get("background") else None
    return LoadedModel(entry["name"], entry["version"], pipeline, entry.get("metrics", {}), background)
