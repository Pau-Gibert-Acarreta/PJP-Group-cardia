"""Reentrenamiento periódico (bloque 4A): extrae datos con etiquetas, entrena un Challenger,
lo evalúa contra el Champion y lo promociona solo si mejora.

    uv run python -m cardia_ml.train            # reentrena y promociona si mejora el AUC de test
    uv run python -m cardia_ml.train --init     # registra el modelo congelado del equipo como Champion

El pipeline es el ganador de la búsqueda del equipo (experiments/coxph/best_pipeline.py) y los
datos son los mismos que leía de raw.csv/parquet, ahora desde la base de datos (cardia_ml.data).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone

import joblib
import numpy as np

from . import data
from .model import ML_ROOT, MODELS_DIR, REGISTRY

BEST_PIPELINE = ML_ROOT / "experiments" / "coxph" / "best_pipeline.py"
FROZEN_FILE = "coxph_score2_v1.joblib"
BACKGROUND_ROWS = 100


def build_pipeline():
    spec = importlib.util.spec_from_file_location("best_pipeline", BEST_PIPELINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_pipeline()


def evaluate(pipeline, X_test, y_test) -> dict:
    from sklearn.metrics import roc_auc_score
    return {"test_roc_auc": round(float(roc_auc_score(y_test, pipeline.predict(X_test))), 4),
            "test_patients": int(len(y_test)), "test_events": int(y_test.sum())}


def _save_background(X_train, version: str) -> str:
    name = f"{version}_background.parquet"
    X_train.sample(n=min(BACKGROUND_ROWS, len(X_train)), random_state=0).reset_index(drop=True) \
        .to_parquet(MODELS_DIR / name, index=False)
    return name


def _load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"champion": None, "models": []}


def _save_registry(reg: dict) -> None:
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def init_champion() -> dict:
    """Registra el modelo ya entrenado por el equipo (pesos congelados) como Champion."""
    raw = data.load_raw()
    _, test_ids = data.train_test_ids(raw)
    X_train, _ = data.training_set(raw, test_ids)
    X_test, y_test, _ = data.test_set(raw, test_ids)
    pipeline = joblib.load(MODELS_DIR / FROZEN_FILE)
    version = "coxph_score2_v1"
    entry = {
        "version": version, "name": "cardia-cv-coxph", "file": FROZEN_FILE,
        "background": _save_background(X_train, version),
        "description": "CoxPH + splines sobre las 6 variables de SCORE2; visitas 1-3, 40-69 años "
                       "(candidato 38 de la búsqueda del equipo)",
        "target": "target_broad_10y", "horizon_years": 10,
        "metrics": {**evaluate(pipeline, X_test, y_test), "cv_roc_auc": 0.6948},
        "trained_rows": int(len(X_train)),
        "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    reg = _load_registry()
    reg["models"] = [m for m in reg["models"] if m["version"] != version] + [entry]
    reg["champion"] = version
    _save_registry(reg)
    return entry


def retrain() -> dict:
    """Entrena un Challenger con los datos actuales y lo promociona si supera al Champion."""
    raw = data.load_raw()
    _, test_ids = data.train_test_ids(raw)
    X_train, y_train = data.training_set(raw, test_ids)
    X_test, y_test, _ = data.test_set(raw, test_ids)
    pipeline = build_pipeline().fit(X_train, y_train)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    version = f"coxph_score2_{stamp}"
    joblib.dump(pipeline, MODELS_DIR / f"{version}.joblib")
    entry = {
        "version": version, "name": "cardia-cv-coxph", "file": f"{version}.joblib",
        "background": _save_background(X_train, version),
        "description": "Reentrenamiento periódico de experiments/coxph/best_pipeline.py desde la base de datos",
        "target": "target_broad_10y", "horizon_years": 10,
        "metrics": evaluate(pipeline, X_test, y_test), "trained_rows": int(len(X_train)),
        "registered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    reg = _load_registry()
    champion = next((m for m in reg["models"] if m["version"] == reg.get("champion")), None)
    promoted = champion is None or entry["metrics"]["test_roc_auc"] > champion["metrics"]["test_roc_auc"]
    entry["status"] = "champion" if promoted else "challenger"
    reg["models"].append(entry)
    if promoted:
        reg["champion"] = version
    _save_registry(reg)
    return {"version": version, "metrics": entry["metrics"], "promoted": promoted,
            "champion": reg["champion"],
            "champion_auc": (champion or entry)["metrics"]["test_roc_auc"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reentrenamiento del modelo de riesgo (4A)")
    parser.add_argument("--init", action="store_true", help="Registra el modelo congelado del equipo como Champion")
    args = parser.parse_args()
    if args.init:
        entry = init_champion()
        print(f"Champion: {entry['version']} | AUC test {entry['metrics']['test_roc_auc']} "
              f"| {entry['trained_rows']} filas de entrenamiento")
        return 0
    result = retrain()
    verdict = "promocionado a Champion" if result["promoted"] else "se queda como Challenger"
    print(f"Challenger {result['version']}: AUC test {result['metrics']['test_roc_auc']} "
          f"(Champion {result['champion_auc']}) -> {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
