"""Motor de reglas: misma semántica que src/domain/findings.js."""
from datetime import datetime, timedelta, timezone

import pytest

from app.clinical_config import ClinicalConfigError, load, validate
from app.rules_engine import Point, evaluate, summarize
from app.settings import get_settings

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
IND = {"systolic": {"field": "systolic", "unit": "mmHg"}, "acr": {"field": "acr", "unit": "mg/g"},
       "egfr": {"field": "egfr", "unit": "mL/min/1,73 m²"}}


def pts(*pairs, unit=None):
    return [Point(v, T0 + timedelta(days=d), unit) for d, v in pairs]


def rule(**kw):
    base = {"id": "r", "field": "systolic", "title": "t", "severity": "warning",
            "conditions": [{"metric": "delta", "operator": "gte", "value": 15}]}
    return base | kw


def test_fires_on_last_two_measurements():
    found = evaluate({"systolic": pts((0, 120), (30, 140))}, IND, [rule()])
    assert len(found) == 1 and found[0].summary.delta == 20 and found[0].interval_days == 30


def test_only_last_two_count():
    # El salto antiguo (120 -> 140) ya no es el último cambio (140 -> 141).
    assert evaluate({"systolic": pts((0, 120), (30, 140), (60, 141))}, IND, [rule()]) == []


def test_needs_two_measurements():
    assert evaluate({"systolic": pts((0, 200))}, IND, [rule()]) == []


def test_max_interval_days():
    data = {"systolic": pts((0, 120), (200, 140))}
    assert evaluate(data, IND, [rule(maxIntervalDays=180)]) == []
    assert len(evaluate(data, IND, [rule(maxIntervalDays=365)])) == 1


def test_all_conditions_and_percent_change():
    acr = rule(field="acr", conditions=[{"metric": "percent_change", "operator": "gte", "value": 50},
                                        {"metric": "delta", "operator": "gte", "value": 10}])
    assert len(evaluate({"acr": pts((0, 20), (30, 31))}, IND, [acr])) == 1   # +55 %, +11
    assert evaluate({"acr": pts((0, 4), (30, 8))}, IND, [acr]) == []         # +100 % pero +4


def test_percent_change_not_evaluated_from_zero():
    r = rule(field="acr", conditions=[{"metric": "percent_change", "operator": "gte", "value": 1}])
    assert summarize("acr", pts((0, 0), (1, 5))).percent_change is None
    assert evaluate({"acr": pts((0, 0), (1, 5))}, IND, [r]) == []


def test_negative_change():
    r = rule(field="egfr", conditions=[{"metric": "percent_change", "operator": "lte", "value": -20}])
    assert len(evaluate({"egfr": pts((0, 80), (60, 60))}, IND, [r])) == 1


def test_disabled_rule_and_unknown_field_ignored():
    data = {"systolic": pts((0, 120), (30, 140))}
    assert evaluate(data, IND, [rule(enabled=False)]) == []
    assert evaluate(data, IND, [rule(field="nope")]) == []


def test_unit_mismatch_and_duplicates():
    data = {"systolic": pts((0, 120), (30, 140), unit="kPa")}
    assert evaluate(data, IND, [rule()]) == []
    # Mismo instante: se conserva la última recibida.
    s = summarize("systolic", pts((0, 100), (0, 120), (30, 140)))
    assert [p.value for p in s.series] == [120, 140]


def test_float_precision_like_js():
    assert summarize("x", pts((0, 0.1), (1, 0.4))).delta == 0.3


def test_repo_rules_file_is_valid():
    s = get_settings()
    cfg = load(s.indicators_path, s.rules_path)
    assert cfg.enabled_rules and cfg.rules_version.startswith("v")


def test_validation_rejects_bad_rule():
    s = get_settings()
    cfg = load(s.indicators_path, s.rules_path)
    bad = {"rules": [rule(conditions=[{"metric": "delta", "operator": "between", "value": 1}])]}
    with pytest.raises(ClinicalConfigError):
        validate(cfg.indicators, bad)
