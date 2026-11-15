"""Ingesta de analíticas en PDF (ETL de documentos).

Por cada PDF:
1. sha256; si ya está en `document`, se salta (idempotente).
2. Se lee el texto y se parsea (nº de petición, CIP, fecha y pruebas).
3. Se identifica al paciente por CIP y el examen por periodo, y se comprueba la fecha.
4. Se comprueba que cada valor impreso coincide con la base de datos, que es la fuente
   de verdad: la ingesta NO crea ni cambia mediciones.
5. Se guardan los bytes (storage.put) y una fila en `document` con lo extraído y la verificación.
6. Se enlaza con la analítica de sangre: su evento de la línea temporal y sus mediciones
   (orina y constantes no tienen informe).

Un PDF que no se puede leer, de un paciente desconocido o con valores que no coinciden
se rechaza y no se enlaza.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from psycopg import Connection

from ..clinical_tests import TEST_KINDS
from . import storage
from .lab_report_parser import LabReportError, matches, parse_pdf


@dataclass
class IngestStats:
    read: int = 0
    ingested: int = 0
    skipped: int = 0
    rejected: list[tuple[str, str]] = field(default_factory=list)   # (archivo, motivo)
    values_checked: int = 0


class Rejected(Exception):
    pass


def ingest_file(conn: Connection, path: Path, batch_id: uuid.UUID | None, stats: IngestStats) -> uuid.UUID | None:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if conn.execute("SELECT 1 FROM document WHERE sha256 = %s", [sha]).fetchone():
        stats.skipped += 1
        return None

    try:
        report = parse_pdf(data)
    except LabReportError as exc:
        raise Rejected(str(exc)) from exc

    patient = conn.execute("SELECT patient_id FROM patient WHERE cip = %s", [report.cip]).fetchone()
    if patient is None or patient["patient_id"] != report.patient_id:
        raise Rejected(f"CIP {report.cip} no corresponde al paciente {report.patient_id}")
    exam = conn.execute("SELECT exam_time FROM exam WHERE patient_id = %s AND period = %s",
                        [report.patient_id, report.period]).fetchone()
    if exam is None:
        raise Rejected(f"El paciente {report.patient_id} no tiene examen del periodo {report.period}")
    if exam["exam_time"].date() != report.extraction_date:
        raise Rejected(f"Fecha {report.extraction_date} distinta de la del examen {exam['exam_time'].date()}")

    stored = {r["indicator_code"]: r["value"] for r in conn.execute("""
        SELECT indicator_code, value FROM measurement
        WHERE patient_id = %s AND measured_at = %s AND indicator_code = ANY(%s)
    """, [report.patient_id, exam["exam_time"], list(report.values)])}
    mismatches = {code: {"pdf": v, "db": stored.get(code)} for code, v in report.values.items()
                  if not matches(code, v, stored.get(code))}
    if mismatches:
        raise Rejected(f"Valores distintos de la base de datos: {mismatches}")
    stats.values_checked += sum(v is not None for v in report.values.values())

    document_id = uuid.uuid4()
    conn.execute("""
        INSERT INTO document (document_id, patient_id, kind, storage_backend, bucket, object_key, content_type,
                              size_bytes, sha256, original_filename, document_date, ocr_status, extracted,
                              ingestion_batch_id)
        VALUES (%s, %s, 'lab_report', 'postgres', %s, %s, 'application/pdf', %s, %s, %s, %s,
                'not_applicable', %s, %s)
    """, [document_id, report.patient_id, storage.RAW_BUCKET,
          storage.object_key(report.patient_id, "lab_report", document_id), len(data), sha, path.name,
          report.extraction_date,
          json.dumps({"request": report.request, "period": report.period, "values": report.values,
                      "verified": True}),
          batch_id])
    storage.put(conn, document_id, data)
    # El informe documenta la analítica de sangre: solo ese evento y sus mediciones apuntan al PDF.
    blood = TEST_KINDS["blood"]
    conn.execute("""
        UPDATE measurement SET document_id = %s
        WHERE patient_id = %s AND measured_at = %s AND indicator_code = ANY(%s)
    """, [document_id, report.patient_id, exam["exam_time"],
          [c for c, v in report.values.items() if v is not None and c in blood.codes]])
    conn.execute("""
        UPDATE clinical_event SET document_id = %s,
               description = 'Informe del laboratorio, nº de petición ' || %s
        WHERE patient_id = %s AND event_time = %s AND test_kind = 'blood'
    """, [document_id, report.request, report.patient_id, exam["exam_time"]])
    stats.ingested += 1
    return document_id


def ingest_folder(conn: Connection, folder: Path, limit: int | None = None) -> IngestStats:
    files = sorted(folder.rglob("*.pdf"))[:limit] if limit else sorted(folder.rglob("*.pdf"))
    stats = IngestStats(read=len(files))
    batch = conn.execute("""
        INSERT INTO ingestion_batch (source_kind, source_uri, rows_read) VALUES ('document', %s, %s)
        RETURNING batch_id
    """, [f"file://{folder.as_posix()}", len(files)]).fetchone()["batch_id"]
    conn.commit()
    for path in files:
        try:
            with conn.transaction():          # un PDF rechazado no deshace los demás
                ingest_file(conn, path, batch, stats)
        except Rejected as exc:
            stats.rejected.append((path.name, str(exc)))
        # Commit por PDF: el progreso se ve en la app al momento y un corte no pierde lo ya ingestado.
        conn.commit()
    conn.execute("""
        UPDATE ingestion_batch SET status = %s, finished_at = now(), rows_loaded = %s, error = %s
        WHERE batch_id = %s
    """, ["succeeded" if not stats.rejected else "failed", stats.ingested,
          json.dumps(stats.rejected[:20], ensure_ascii=False) if stats.rejected else None, batch])
    return stats
