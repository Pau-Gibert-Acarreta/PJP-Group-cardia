"""Construye el índice KNN (exam_embedding, versión knn-v1) y su escalador.

Ejecútalo tras cargar los datos (db/002-005) o tras cambiar variables o pesos:

    uv run python -m app.jobs.build_knn_index
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from ..knn.service import build_index
from ..settings import get_settings


def main() -> int:
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        conn.execute("SET search_path = cardia, public")
        result = build_index(conn)
    print(f"Índice {result['version']}: {result['exams']} exámenes indexados ({result['seconds']} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
