"""Almacén de los bytes de los documentos.

MVP: storage_backend = 'postgres' (tabla document_blob), la opción "Mismo PostgreSQL"
del diagrama. Cada documento rellena igualmente bucket y object_key con la ruta que
tendría en S3, así que pasar a S3 es copiar los bytes y cambiar storage_backend; el
resto del backend solo usa put() y get().
"""
from __future__ import annotations

from uuid import UUID

from psycopg import Connection

RAW_BUCKET = "cardia-raw"


def object_key(patient_id: int, kind: str, document_id: UUID, ext: str = "pdf") -> str:
    """Claves solo con ids (sin nombres ni CIP), como define db/README.md."""
    return f"documents/{patient_id}/{kind}/{document_id}.{ext}"


def put(conn: Connection, document_id: UUID, data: bytes) -> None:
    conn.execute("INSERT INTO document_blob (document_id, content) VALUES (%s, %s)", [document_id, data])


def get(conn: Connection, document: dict) -> bytes:
    if document["storage_backend"] != "postgres":
        raise NotImplementedError("Backend de almacenamiento no configurado: " + document["storage_backend"])
    row = conn.execute("SELECT content FROM document_blob WHERE document_id = %s",
                       [document["document_id"]]).fetchone()
    if row is None:
        raise FileNotFoundError(f"Documento {document['document_id']} sin contenido")
    return bytes(row["content"])
