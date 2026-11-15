"""Analíticas PDF: generación desde la base de datos, parser, ingesta y endpoints.

Requieren la base de datos cargada; si no está, se omiten. Los PDF se generan en una
carpeta temporal; al final, los pacientes de prueba vuelven a quedar con sus informes.
"""
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.documents.ingest import IngestStats, Rejected, ingest_file, ingest_folder
from app.documents.lab_report_parser import LabReportError, matches, parse_pdf, parse_text
from app.jobs.generate_lab_reports import generar
from app.settings import get_settings

PIDS = [2448, 19304]   # 2448: exámenes 1 y 3; 19304: un solo examen


def _db():
    try:
        conn = psycopg.connect(get_settings().database_url, row_factory=dict_row, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Base de datos no disponible")
    conn.execute("SET search_path = cardia, public")
    return conn


def _cleanup(conn):
    docs = [r["document_id"] for r in conn.execute("SELECT document_id FROM document WHERE patient_id = ANY(%s)", [PIDS])]
    conn.execute("UPDATE measurement SET document_id = NULL WHERE document_id = ANY(%s)", [docs])
    conn.execute("UPDATE clinical_event SET document_id = NULL, description = NULL WHERE document_id = ANY(%s)", [docs])
    conn.execute("DELETE FROM document WHERE document_id = ANY(%s)", [docs])
    conn.commit()


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("lab_reports")
    conn = _db()
    _cleanup(conn)
    paths = generar(conn, PIDS, folder)
    yield folder, paths, conn
    # Deja a los pacientes como estaban: con sus informes ingestados (mismos bytes que los de
    # data/landing, así que la ingesta completa los seguirá considerando ya existentes).
    _cleanup(conn)
    ingest_folder(conn, folder)
    conn.commit()
    conn.close()


def test_generator_prints_database_values(pdfs):
    folder, paths, conn = pdfs
    assert len(paths) == 3
    p3 = next(p for p in paths if "2448_periodo3" in p.name)
    report = parse_pdf(p3.read_bytes())
    assert (report.patient_id, report.period, report.cip) == (2448, 3, "SYN0002448")
    assert report.extraction_date == date(2025, 9, 3)        # misma fecha que exam_time
    stored = {r["indicator_code"]: r["value"] for r in conn.execute("""
        SELECT m.indicator_code, m.value FROM measurement m JOIN exam e
          ON e.patient_id = m.patient_id AND e.exam_time = m.measured_at
        WHERE e.patient_id = 2448 AND e.period = 3""")}
    for code, printed in report.values.items():
        assert matches(code, printed, stored.get(code)), code
    assert report.values["hdl_cholesterol"] == 31 and report.values["ldl"] == 178


def test_missing_values_are_not_determined(pdfs):
    _, paths, _ = pdfs
    p1 = next(p for p in paths if "2448_periodo1" in p.name)
    values = parse_pdf(p1.read_bytes()).values
    assert values["hdl_cholesterol"] is None and values["ldl"] is None   # en Framingham, solo en el periodo 3


def test_generation_is_deterministic(pdfs, tmp_path):
    folder, paths, conn = pdfs
    again = generar(conn, [2448], tmp_path)
    original = {p.name: p.read_bytes() for p in paths}
    assert all(p.read_bytes() == original[p.name] for p in again)        # mismos bytes -> mismo sha256


def test_ingest_links_and_is_idempotent(pdfs):
    folder, _, conn = pdfs
    first = ingest_folder(conn, folder)
    conn.commit()
    assert (first.ingested, first.skipped, first.rejected) == (3, 0, [])
    second = ingest_folder(conn, folder)
    conn.commit()
    assert (second.ingested, second.skipped) == (0, 3)
    linked = conn.execute("""
        SELECT count(*) AS n FROM measurement m JOIN document d ON d.document_id = m.document_id
        WHERE d.patient_id = 2448 AND m.indicator_code = 'hba1c'""").fetchone()["n"]
    assert linked == 2
    event = conn.execute("""SELECT document_id FROM clinical_event
                            WHERE patient_id = 19304 AND event_type = 'exam'""").fetchone()
    assert event["document_id"] is not None


def test_ingest_rejects_values_that_do_not_match(pdfs, tmp_path):
    _, paths, conn = pdfs
    text_ok = "\n".join([
        "Nº de petición: 2448-3", "Fecha de extracción: 03/09/2025", "CIP:", "SYN0002448",
        "Glucosa", "Suero · determinación casual", "92", "Hemoglobina glicada (HbA1c)", "9,9",
        "Creatinina", "1,03", "Filtrado glomerular estimado", "CKD-EPI 2021", "87",
        "Colesterol total", "209", "Colesterol HDL", "31", "Colesterol LDL", "178",
        "Cociente albúmina/creatinina", "9,0",
    ])
    report = parse_text(text_ok)
    assert report.values["hba1c"] == 9.9 and report.values["glucose"] == 92
    with pytest.raises(LabReportError):
        parse_text("Un PDF cualquiera")
    bad = tmp_path / "otro.pdf"
    bad.write_bytes(b"%PDF-1.4 no es una analitica")
    with pytest.raises(Rejected):
        ingest_file(conn, bad, None, IngestStats())
    conn.rollback()


def test_document_endpoints(pdfs):
    folder, _, conn = pdfs
    ingest_folder(conn, folder)
    conn.commit()
    from app.main import app
    with TestClient(app) as client:
        docs = client.get("/api/v1/patients/2448/documents").json()
        assert [d["date"] for d in docs] == ["2025-09-03", "2013-01-01"]
        assert "objectKey" not in docs[0] and "bucket" not in docs[0]
        pdf = client.get(docs[0]["contentUrl"])
        assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF") and "inline" in pdf.headers["content-disposition"]
        event = next(e for e in client.get("/api/v1/patients/2448/events").json() if e["title"] == "Examen 3")
        assert event["documentId"] == docs[0]["id"]
        assert client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000").status_code == 404
