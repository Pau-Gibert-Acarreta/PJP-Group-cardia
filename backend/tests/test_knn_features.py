"""Vector de un caso: estado en t, tendencias y escalado (sin base de datos)."""
import math
from datetime import datetime, timezone

import pytest

from app.knn.features import DIMENSIONS, FEATURES, PatientHistory, Scaler, state_at

T = lambda y, m=1, d=1: datetime(y, m, d, tzinfo=timezone.utc)  # noqa: E731


def exam(t, age, **kw):
    base = dict(exam_time=t, age_years=age, current_smoker=False, cigs_per_day=0, diabetes=False,
                bp_meds=False, prev_hypertension=False, prev_chd=False, prev_stroke=False)
    return base | kw


@pytest.fixture
def history():
    return PatientHistory(1, "M",
                          exams=[exam(T(2013), 50), exam(T(2019), 56, current_smoker=True, cigs_per_day=10)],
                          series={"systolic": [(T(2013), 120.0), (T(2019), 138.0), (T(2025), 150.0)],
                                  "bmi": [(T(2013), 25.0)]})


def test_dimensions_match_database():
    assert DIMENSIONS == len(FEATURES) == 20


def test_state_uses_only_data_up_to_t(history):
    s = state_at(history, T(2019))
    assert s["systolic"] == 138.0 and s["current_smoker"] == 1.0 and s["sex"] == 1.0
    assert s["systolic_trend"] == pytest.approx(18 / 6, rel=1e-3)   # +18 mmHg en 6 años
    assert s["bmi"] == 25.0 and s["bmi_trend"] is None               # una sola medición: sin tendencia
    assert s["hdl_cholesterol"] is None


def test_state_after_new_test_ages_patient(history):
    s = state_at(history, T(2025))
    assert s["systolic"] == 150.0 and s["age_years"] == pytest.approx(62, abs=0.01)
    assert s["systolic_trend"] == pytest.approx(2.0, rel=1e-2)       # 138 -> 150 en 6 años
    assert state_at(history, T(2010)) is None                        # antes del primer examen


def test_test_times_include_exams_and_measurements(history):
    assert history.test_times() == [T(2013), T(2019), T(2025)]


def test_scaler_weights_and_missing_values(history):
    states = [state_at(history, T(2013)), state_at(history, T(2019)), state_at(history, T(2025))]
    scaler = Scaler.fit(states)
    z = scaler.z(states[0])
    vec = scaler.vector(states[0])
    i = [f.key for f in FEATURES].index("systolic")
    assert vec[i] == pytest.approx(z[i] * math.sqrt(FEATURES[i].weight))
    j = [f.key for f in FEATURES].index("hdl_cholesterol")
    assert z[j] == 0.0                                               # ausente -> media
    assert Scaler.from_json(scaler.to_json()).means == scaler.means


def test_scaler_rejects_other_weights(history):
    data = Scaler.fit([state_at(history, T(2019))]).to_json()
    data[0]["weight"] = 99
    with pytest.raises(ValueError):
        Scaler.from_json(data)


def test_only_original_framingham_variables():
    # HbA1c, creatinina, eGFR y ACR son sintéticos en esta base de datos (db/004).
    synthetic = {"hba1c", "serum_creatinine", "egfr", "acr"}
    assert not {f.source for f in FEATURES} & synthetic
    assert not {f.key for f in FEATURES} & synthetic
