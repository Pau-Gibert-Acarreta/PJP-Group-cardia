"""Modelo de riesgo: mismas variables que el CSV, modelo congelado, SHAP, reentrenamiento y servicio.

Las pruebas que leen la base de datos se omiten si no está disponible.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cardia_ml import data, explain
from cardia_ml.model import load

ML = Path(__file__).resolve().parents[1]
RAW_CSV = ML.parent / "data" / "raw.csv"
REFERENCE = ML / "experiments" / "coxph" / "test_predictions.csv"


@pytest.fixture(scope="module")
def raw():
    try:
        return data.load_raw()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Base de datos no disponible: {exc}")


@pytest.mark.skipif(not RAW_CSV.exists(), reason="data/raw.csv no está (no se versiona)")
def test_database_gives_exactly_raw_csv(raw):
    csv = pd.read_csv(RAW_CSV, na_values=["."]).astype(float)[data.RAW_COLUMNS]
    a = raw.sort_values(["RANDID", "PERIOD"]).reset_index(drop=True)
    b = csv.sort_values(["RANDID", "PERIOD"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def test_split_matches_teammate_test_set(raw):
    _, test_ids = data.train_test_ids(raw)
    assert set(test_ids) == set(pd.read_csv(REFERENCE).patient_id)


def test_frozen_model_reproduces_teammate_predictions(raw):
    _, test_ids = data.train_test_ids(raw)
    X, _, ids = data.test_set(raw, test_ids)
    pred = pd.DataFrame({"patient_id": ids, "pred": load().risk_score(X)})
    ref = pd.read_csv(REFERENCE).merge(pred, on="patient_id")
    assert len(ref) == 454
    assert np.abs(ref.pred - ref.risk_score).max() < 1e-9


def test_training_data_reproduces_frozen_weights(raw):
    from cardia_ml.train import build_pipeline
    _, test_ids = data.train_test_ids(raw)
    X, y = data.training_set(raw, test_ids)
    assert len(X) == 7871 and int(y[:, 0].sum()) == 1078
    refit = build_pipeline().fit(X, y)
    assert np.abs(refit.named_steps["model"].model_.coef_ - load().cox.coef_).max() < 1e-8


def _features(**kw):
    base = {"age_years": 52, "sex": "M", "current_smoker": False, "systolic": 121,
            "total_cholesterol": 209, "hdl_cholesterol": 31}
    return data.features_from_backend({**base, **kw})


def test_probability_and_units():
    m = load()
    p = m.probability(_features())[0]
    assert 0 < p < 1
    assert m.probability(_features(systolic=180))[0] > p          # más presión, más riesgo
    assert m.probability(_features(current_smoker=True))[0] > p    # fumar aumenta el riesgo
    X = _features()
    assert X.total_cholesterol[0] == pytest.approx(209 / 38.67)     # mg/dL -> mmol/L como en el entrenamiento
    assert np.isnan(_features(hdl_cholesterol=None).hdl_cholesterol[0])   # ausente -> lo imputa el modelo


def test_shap_is_exact_and_additive():
    m = load()
    X = _features()
    base, phi = explain.shap_values(m.risk_score, X, m.background)
    assert base + phi.sum() == pytest.approx(m.risk_score(X)[0], abs=1e-9)   # propiedad de eficiencia
    top = explain.top_k(X, phi)
    assert [t["feature"] for t in top][0] == X.columns[np.argmax(np.abs(phi))]
    chol = next(t for t in top if t["feature"] == "total_cholesterol")
    assert chol["value"] == 209 and chol["unit"] == "mg/dL"                # se muestra en unidades de la app


def test_service_predict_contract():
    from fastapi.testclient import TestClient
    import service
    with TestClient(service.app) as client:
        r = client.post("/v1/predict", json={"patientId": "2448", "features": {
            "age_years": 52, "sex": "M", "current_smoker": False, "systolic": 121,
            "total_cholesterol": 209, "hdl_cholesterol": 31}})
        assert r.status_code == 200
        body = r.json()
        assert set(body) >= {"probability", "modelName", "modelVersion", "horizonYears", "shapBaseValue", "shapTopK"}
        assert body["modelVersion"] == load().version and body["horizonYears"] == 10
        assert len(body["shapTopK"]) == 6
        assert client.post("/v1/predict", json={"patientId": "1", "features": {}}).status_code == 422
        assert client.post("/v1/predict", json={"patientId": "1", "target": "renal", "features": {}}).status_code == 422


def test_retrain_keeps_champion_unless_better(raw, tmp_path, monkeypatch):
    from cardia_ml import train
    registry = json.loads((ML / "models" / "registry.json").read_text(encoding="utf-8"))
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(train, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(train, "REGISTRY", tmp_path / "registry.json")
    result = train.retrain()
    assert result["metrics"]["test_roc_auc"] == pytest.approx(0.6636, abs=1e-4)   # mismos datos -> mismo modelo
    assert result["promoted"] is False and result["champion"] == "coxph_score2_v1"
    saved = json.loads((tmp_path / "registry.json").read_text(encoding="utf-8"))
    assert saved["models"][-1]["status"] == "challenger"
