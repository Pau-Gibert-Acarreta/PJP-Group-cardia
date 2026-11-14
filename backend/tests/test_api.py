"""Pruebas de integración contra la base de datos cargada (db/001-004).

Requieren PostgreSQL accesible en CARDIA_DATABASE_URL; si no lo está, se omiten.
Todo lo que escriben (pruebas nuevas, notas, ajustes, predicciones) se borra al final.
"""
from datetime import datetime, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import risk_service
from app.settings import get_settings

PID = 2448
TEST_TIME = "2025-12-01T09:00:00Z"
KEY = "test-ml-key"


def _db_available() -> bool:
    try:
        psycopg.connect(get_settings().database_url, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Base de datos no disponible")


def _cleanup():
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute("SET search_path = cardia")
        conn.execute("DELETE FROM measurement WHERE patient_id = %s AND measured_at > '2025-10-01'", [PID])
        conn.execute("DELETE FROM clinical_event WHERE patient_id = %s AND event_time > '2025-10-01'", [PID])
        conn.execute("DELETE FROM finding WHERE patient_id = %s", [PID])
        conn.execute("DELETE FROM clinical_note WHERE patient_id = %s", [PID])
        conn.execute("DELETE FROM risk_classification_override WHERE patient_id = %s", [PID])
        conn.execute("DELETE FROM patient_followup WHERE patient_id = %s", [PID])
        conn.execute("DELETE FROM risk_prediction WHERE patient_id = %s", [PID])
        conn.execute("DELETE FROM exam_embedding WHERE embedding_version = 'pytest'")


@pytest.fixture(scope="module")
def client(monkeypatch_module):
    monkeypatch_module.setenv("CARDIA_ML_API_KEY", KEY)
    monkeypatch_module.setenv("CARDIA_ML_RISK_URL", "http://ml.test")
    get_settings.cache_clear()
    _cleanup()
    from app.main import app
    with TestClient(app) as c:
        yield c
    _cleanup()
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_list_patients_contract(client):
    body = client.get("/api/v1/patients", params={"limit": 5, "sort": "name"}).json()
    assert body["total"] == 4434 and len(body["items"]) == 5
    p = body["items"][0]
    for key in ("id", "cip", "name", "age", "sex", "risk", "followup", "lastTest", "conditions", "measurements"):
        assert key in p
    assert p["sex"] in ("Hombre", "Mujer")
    point = next(iter(p["measurements"].values()))[0]
    assert set(point) >= {"value", "date", "unit"}


def test_list_filters(client):
    hta = client.get("/api/v1/patients", params={"condition": "Hipertensión", "limit": 1}).json()
    women = client.get("/api/v1/patients", params={"sex": "Mujer", "age": "65plus", "limit": 1}).json()
    search = client.get("/api/v1/patients", params={"q": "SYN0002448"}).json()
    assert 0 < hta["total"] < 4434 and 0 < women["total"] < 4434
    assert search["total"] == 1 and search["items"][0]["id"] == str(PID)


def test_patient_detail(client):
    p = client.get(f"/api/v1/patients/{PID}").json()
    assert p["id"] == "2448" and p["age"] == 52 and p["email"].endswith("@example.test")
    assert [m["value"] for m in p["measurements"]["systolic"]] == [106, 121]
    assert p["events"] and p["findings"] == [] and p["risk"] is None


def test_unknown_patient_404(client):
    assert client.get("/api/v1/patients/1").status_code == 404


def test_rules_config_endpoint(client):
    body = client.get("/api/v1/config/rules").json()
    assert body["rulesVersion"].startswith("v") and any(r["id"] == "systolic-rise" for r in body["rules"])


def test_new_test_creates_finding_and_risk(client, monkeypatch_module):
    sent = {}

    def fake_post(url, payload, timeout):
        sent.update(url=url, payload=payload)
        return {"probability": 0.231, "modelName": "fake", "modelVersion": "0.0.1", "horizonYears": 10,
                "shapTopK": [{"feature": "systolic", "label": "PA sistólica", "value": 140,
                              "unit": "mmHg", "contribution": 0.05}]}

    monkeypatch_module.setattr(risk_service, "_post", fake_post)
    # Último systolic: 121 el 2025-09-03. 140 el 2025-12-01 = +19 en 89 días -> systolic-rise.
    r = client.post(f"/api/v1/patients/{PID}/tests",
                    json={"takenAt": TEST_TIME, "values": {"systolic": 140, "diastolic": 70}})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["findings"]["created"] == 1
    assert [f["ruleId"] for f in body["findings"]["active"]] == ["systolic-rise"]
    assert body["findings"]["active"][0]["delta"] == 19
    assert body["risk"][0]["status"] == "stored" and sent["url"] == "http://ml.test/v1/predict"
    assert sent["payload"]["features"]["systolic"] == 140
    assert "cvd" not in sent["payload"]["features"]  # nunca etiquetas en serving

    p = client.get(f"/api/v1/patients/{PID}").json()
    assert p["risk"] == 23.1 and p["riskLevel"] == "high" and p["activeFindings"] == 1
    assert p["factors"][0]["weight"] == 100

    # Repetir la misma prueba: conflicto, no duplica.
    again = client.post(f"/api/v1/patients/{PID}/tests",
                        json={"takenAt": TEST_TIME, "values": {"systolic": 140}})
    assert again.status_code == 409


def test_finding_resolves_when_rule_stops_matching(client):
    r = client.post(f"/api/v1/patients/{PID}/tests",
                    json={"takenAt": "2025-12-15T09:00:00Z", "values": {"systolic": 141},
                          "recalculateRisk": False})
    body = r.json()
    assert body["findings"]["resolved"] == 1 and body["findings"]["active"] == []


def test_new_test_validation(client):
    assert client.post(f"/api/v1/patients/{PID}/tests", json={"values": {"nope": 1}}).status_code == 422
    assert client.post(f"/api/v1/patients/{PID}/tests", json={"values": {}}).status_code == 422
    future = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    assert client.post(f"/api/v1/patients/{PID}/tests",
                       json={"takenAt": future, "values": {"systolic": 1}}).status_code == 422


def test_risk_classification_flow(client):
    url = f"/api/v1/patients/{PID}/risk-classification"
    assert client.put(url, json={"level": "low"}).status_code == 422          # sin motivo
    r = client.put(url, json={"level": "low", "reason": "Revisión"}, headers={"X-Clinician": "Dr. Test"})
    assert r.json()["riskOverride"] == {**r.json()["riskOverride"], "level": "low", "modelLevel": "high",
                                        "author": "Dr. Test"}
    assert client.get(f"/api/v1/patients/{PID}").json()["effectiveRiskLevel"] == "low"
    assert client.put(url, json={"level": "high"}).json()["riskOverride"] is None  # = modelo: elimina
    assert client.delete(url).status_code == 204


def test_followup_and_notes(client):
    assert client.put(f"/api/v1/patients/{PID}/followup", json={"followup": True}).json() == {"followup": True}
    note = client.post(f"/api/v1/patients/{PID}/notes", json={"text": "  Primera nota  "}).json()
    assert note["text"] == "Primera nota" and note["author"] == "Dra. Carmen Vidal"
    upd = client.put(f"/api/v1/patients/{PID}/notes/{note['id']}", json={"text": "Editada"}).json()
    assert upd["text"] == "Editada"
    assert client.post(f"/api/v1/patients/{PID}/notes", json={"text": "   "}).status_code == 422
    listed = client.get(f"/api/v1/patients", params={"q": "SYN0002448"}).json()["items"][0]
    assert listed["followup"] is True


def test_ml_requires_key(client):
    assert client.get(f"/api/v1/ml/patients/{PID}/features").status_code == 401
    ok = client.get(f"/api/v1/ml/patients/{PID}/features", headers={"X-API-Key": KEY})
    assert ok.status_code == 200 and "cvd" not in ok.json()["features"]


def test_ml_training_set_pagination(client):
    h = {"X-API-Key": KEY}
    first = client.get("/api/v1/ml/training-set", params={"limit": 3}, headers=h).json()
    assert len(first["items"]) == 3 and {"event", "days_to_event"} <= set(first["items"][0])
    second = client.get("/api/v1/ml/training-set", params={"limit": 3, **first["next"]}, headers=h).json()
    assert second["items"][0]["patient_id"] >= first["items"][-1]["patient_id"]
    assert all(i["days_to_event"] >= 0 for i in first["items"] + second["items"])


def test_ml_embeddings_roundtrip(client):
    h = {"X-API-Key": KEY}
    exams = client.get(f"/api/v1/patients/{PID}/events").json()
    v1, v2 = [0.0] * 16, [1.0] * 16
    items = [{"patientId": PID, "examTime": "2013-01-01T00:00:00Z", "embedding": v1},
             {"patientId": 6238, "examTime": "2013-01-01T00:00:00Z", "embedding": v2}]
    assert client.put("/api/v1/ml/embeddings", json={"version": "pytest", "items": items},
                      headers=h).json()["upserted"] == 2
    hits = client.post("/api/v1/ml/embeddings/search",
                       json={"version": "pytest", "embedding": [0.1] * 16, "k": 2}, headers=h).json()
    assert [x["patientId"] for x in hits] == ["2448", "6238"]
    excl = client.post("/api/v1/ml/embeddings/search",
                       json={"version": "pytest", "embedding": v1, "excludePatientId": PID}, headers=h).json()
    assert [x["patientId"] for x in excl] == ["6238"]
    assert exams  # el paciente tiene línea temporal
