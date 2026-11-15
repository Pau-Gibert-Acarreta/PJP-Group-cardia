"""ETL: construcción de fuentes y carga (sin base de datos, salvo la última prueba)."""
import csv
from datetime import date

import pytest

from app.etl.load import LOINC_TO_INDICATOR, EtlError, egfr_ckd_epi_2021, load
from app.etl.sources import LOINC, build, identity, rnd, synthetic_labs, u

RAW_HEADER = ("RANDID,SEX,TOTCHOL,AGE,SYSBP,DIABP,CURSMOKE,CIGPDAY,BMI,DIABETES,BPMEDS,HEARTRTE,GLUCOSE,educ,"
              "PREVCHD,PREVAP,PREVMI,PREVSTRK,PREVHYP,TIME,PERIOD,HDLC,LDLC,DEATH,ANGINA,HOSPMI,MI_FCHD,ANYCHD,"
              "STROKE,CVD,HYPERTEN,TIMEAP,TIMEMI,TIMEMIFC,TIMECHD,TIMESTRK,TIMECVD,TIMEDTH,TIMEHYP")
# Primeras filas reales de raw.csv (paciente 2448, exámenes 1 y 3)
RAW_ROWS = [
    "2448,1,195,39,106,70,0,0,26.97,0,0,80,77,4,0,0,0,0,0,0,1,,,0,0,1,1,1,0,1,0,8766,6438,6438,6438,8766,6438,8766,8766",
    "2448,1,209,52,121,66,0,0,,0,0,69,92,4,0,0,0,0,0,4628,3,31,178,0,0,1,1,1,0,1,0,8766,6438,6438,6438,8766,6438,8766,8766",
]


@pytest.fixture
def raw(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(RAW_HEADER + "\n" + "\n".join(RAW_ROWS) + "\n", encoding="utf-8")
    return path


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_random_matches_postgres_md5():
    # Mismo valor que ('x'||substr(md5('2448:first'),1,8))::bit(32)::bigint / 2^32 en PostgreSQL
    assert u("2448:first") == pytest.approx(0.7163360517006367)


def test_identity_is_deterministic_and_fake():
    p = identity(2448, "1")
    assert p == {"first_name": "Víctor", "last_name": "Torres Cortés", "cip": "SYN0002448",
                 "phone": "630 936 362", "email": "victor.torres.2448@example.test"}


def test_rounding_like_postgres():
    assert rnd(2.25, 1) == 2.3 and rnd(0.5, 0) == 1.0     # hacia fuera, no al par


def test_synthetic_labs_match_previous_database():
    # Valores que tenía la base de datos para 2448, examen 3
    labs = synthetic_labs(2448, 3, "1", 52, False, False, 92.0, 121.0)
    assert labs == {"hba1c": 5.6, "creatinine": 1.03, "acr": 9.0}
    assert rnd(egfr_ckd_epi_2021(1.03, 52, False), 0) == 87


def test_build_writes_separate_sources(raw, tmp_path):
    counts = build(raw, tmp_path / "sources")
    assert counts == {"ehr_patients.csv": 1, "ehr_visits.csv": 2, "data_pressure.csv": 2,
                      "data_blood.csv": 10, "data_urine.csv": 2, "registry_outcomes.csv": 1}
    blood = read(tmp_path / "sources" / "data_blood.csv")
    assert {r["loinc"] for r in blood} <= set(LOINC)
    assert not any(r["loinc"] == "2085-9" and r["study_day"] == "0" for r in blood)   # HDL ausente: sin fila
    pressure = read(tmp_path / "sources" / "data_pressure.csv")
    assert pressure[1]["bmi_kg_m2"] == "" and pressure[1]["systolic_mmhg"] == "121"
    assert set(LOINC) == set(LOINC_TO_INDICATOR)                                       # todo LOINC tiene destino


def test_load_rejects_unmapped_loinc(raw, tmp_path):
    sources = tmp_path / "sources"
    build(raw, sources)
    blood = (sources / "data_blood.csv").read_text(encoding="utf-8").replace("2345-7", "9999-9")
    (sources / "data_blood.csv").write_text(blood, encoding="utf-8")

    class FakeConn:   # el error salta antes de llegar a esa fuente sin tocar datos reales
        def __init__(self): self.calls = []
        def execute(self, *a, **k): self.calls.append(a); return self
        def fetchone(self): return {"exists": False, "batch_id": "b", "n": 0}
        def cursor(self): return self
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def executemany(self, *a): pass

    with pytest.raises(EtlError, match="LOINC sin mapear"):
        load(FakeConn(), sources, date(2013, 1, 1))
