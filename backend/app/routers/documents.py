"""Documentos clínicos: metadatos y contenido (PDF de las analíticas).

El navegador nunca recibe bucket ni object_key: pide el documento por su id y el
backend entrega los bytes desde el almacén (hoy PostgreSQL, mañana S3).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response

from ..deps import Conn, PatientId
from ..documents import storage
from ..formatting import iso

router = APIRouter(tags=["documentos"])

KIND_LABELS = {"lab_report": "Informe de laboratorio", "clinical_report": "Informe clínico", "ecg": "ECG",
               "imaging": "Imagen", "tabular_extract": "Extracto de datos", "other": "Otro"}


def _metadata(row: dict) -> dict:
    return {
        "id": str(row["document_id"]),
        "patientId": str(row["patient_id"]) if row["patient_id"] else None,
        "kind": row["kind"],
        "kindLabel": KIND_LABELS.get(row["kind"], row["kind"]),
        "date": iso(row["document_date"]),
        "contentType": row["content_type"],
        "sizeBytes": row["size_bytes"],
        "filename": row["original_filename"],
        "request": (row["extracted"] or {}).get("request"),
        "contentUrl": f"/api/v1/documents/{row['document_id']}/content",
    }


def _document(conn, document_id: UUID) -> dict:
    row = conn.execute("SELECT * FROM document WHERE document_id = %s", [document_id]).fetchone()
    if row is None:
        raise HTTPException(404, "Documento no encontrado")
    return row


@router.get("/patients/{patient_id}/documents")
def patient_documents(patient_id: PatientId, conn: Conn):
    rows = conn.execute("""
        SELECT * FROM document WHERE patient_id = %s ORDER BY document_date DESC NULLS LAST, created_at DESC
    """, [patient_id]).fetchall()
    return [_metadata(r) for r in rows]


@router.get("/documents/{document_id}")
def document_metadata(document_id: UUID, conn: Conn):
    return _metadata(_document(conn, document_id))


@router.get("/documents/{document_id}/content")
def document_content(document_id: UUID, conn: Conn):
    row = _document(conn, document_id)
    try:
        data = storage.get(conn, row)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc))
    filename = row["original_filename"] or f"{document_id}.pdf"
    return Response(data, media_type=row["content_type"], headers={
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "private, max-age=3600",
        "X-Content-Type-Options": "nosniff",
    })
