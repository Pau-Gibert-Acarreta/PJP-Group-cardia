"""Carga las fuentes de data/sources/ en la base de datos (ETL).

    uv run python -m app.jobs.load_sources --reset        # vacía la base de datos y carga desde cero
    uv run python -m app.jobs.load_sources --reset --baseline 2013-01-01

--reset borra el esquema cardia (pacientes, notas, hallazgos, documentos, todo) y lo
vuelve a crear con db/001_schema.sql y db/005_knn.sql. Sin --reset, se niega a cargar
sobre una base de datos con pacientes.

Después de cargar, para tener la app completa:
    uv run python -m app.jobs.evaluate_findings
    uv run python -m app.jobs.build_knn_index
    uv run python -m app.jobs.generate_lab_reports --all && uv run python -m app.jobs.ingest_lab_reports
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ..etl.load import load, reset_schema
from ..settings import get_settings
from .build_sources import SOURCES


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga data/sources/ en la base de datos")
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--baseline", type=date.fromisoformat, default=date(2013, 1, 1),
                        help="Fecha del día 0 de estudio (por defecto 2013-01-01)")
    parser.add_argument("--reset", action="store_true", help="Vacía la base de datos antes de cargar")
    args = parser.parse_args()
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        if args.reset:
            reset_schema(conn)
        conn.execute("SET search_path = cardia, public")
        stats = load(conn, args.sources, args.baseline)
    for table, n in stats.rows.items():
        print(f"  {table:<16} {n:>7} filas")
    print(f"Carga completada ({stats.seconds} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
