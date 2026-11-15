"""Ingesta las analíticas PDF de la carpeta de entrada.

    uv run python -m app.jobs.ingest_lab_reports                      # data/landing/lab_reports
    uv run python -m app.jobs.ingest_lab_reports --folder otra/carpeta --limit 50

Idempotente: los PDF ya ingestados (mismo sha256) se saltan.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ..documents.ingest import ingest_folder
from ..settings import get_settings
from .generate_lab_reports import SALIDA


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta analíticas PDF")
    parser.add_argument("--folder", type=Path, default=SALIDA)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    start = time.perf_counter()
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        conn.execute("SET search_path = cardia, public")
        stats = ingest_folder(conn, args.folder, args.limit)
    print(f"{stats.read} PDF leídos: {stats.ingested} ingestados, {stats.skipped} ya existían, "
          f"{len(stats.rejected)} rechazados; {stats.values_checked} valores verificados contra la base de datos "
          f"({time.perf_counter() - start:.1f} s)")
    for name, reason in stats.rejected[:10]:
        print(f"  ✗ {name}: {reason}")
    return 1 if stats.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
