"""Recalcula los hallazgos de todos los pacientes (o de los indicados).

Úsalo tras cargar datos o tras cambiar rules.json:

    uv run python -m app.jobs.evaluate_findings            # todos
    uv run python -m app.jobs.evaluate_findings 2448 6238  # algunos
"""
from __future__ import annotations

import sys
import time

import psycopg
from psycopg.rows import dict_row

from .. import findings_service
from ..clinical_config import load
from ..settings import get_settings


def main(argv: list[str]) -> int:
    settings = get_settings()
    config = load(settings.indicators_path, settings.rules_path)
    ids = [int(a) for a in argv] or None
    start = time.perf_counter()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        conn.execute("SET search_path = cardia, public")
        stats = findings_service.refresh(conn, config, ids)
    print(f"Reglas {config.rules_version}: {stats.patients} pacientes, {stats.created} hallazgos nuevos, "
          f"{stats.resolved} cerrados, {stats.relabeled} actualizados, {stats.active} activos "
          f"({time.perf_counter() - start:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
