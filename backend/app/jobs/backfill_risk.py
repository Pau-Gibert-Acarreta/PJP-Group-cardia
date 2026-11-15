"""Calcula y guarda la predicción de riesgo de todos los pacientes (trigger 'backfill').

Necesita el Motor de Riesgo (ml/service.py) en marcha y CARDIA_ML_RISK_URL apuntando a él:

    uv run python -m app.jobs.backfill_risk                       # todos
    uv run python -m app.jobs.backfill_risk --only-missing        # solo los que no tienen predicción
    CARDIA_ML_RISK_URL=http://127.0.0.1:8001 uv run python -m app.jobs.backfill_risk

Usa el mismo camino que el evento "Nueva prueba" (risk_service.recalculate), en paralelo.
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import psycopg
from psycopg.rows import dict_row

from .. import risk_service
from ..settings import get_settings


def _worker(ids: list[int], settings) -> Counter:
    stats: Counter = Counter()
    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        conn.execute("SET search_path = cardia, public")
        for pid in ids:
            for result in risk_service.recalculate(conn, pid, settings, trigger="backfill"):
                stats[result["status"]] += 1
                if result["status"] == "failed" and stats["failed"] <= 3:
                    print(f"  ✗ {pid}: {result.get('error')}")
            conn.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Predicción de riesgo para todo el cupo")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    settings = get_settings()
    if not settings.ml_risk_url:
        parser.error("Define CARDIA_ML_RISK_URL (p. ej. http://127.0.0.1:8001)")
    with psycopg.connect(settings.database_url) as conn:
        sql = "SELECT patient_id FROM cardia.patient"
        if args.only_missing:
            sql += " WHERE patient_id NOT IN (SELECT patient_id FROM cardia.risk_prediction WHERE target = 'cv')"
        ids = [r[0] for r in conn.execute(sql + " ORDER BY patient_id")]
    start = time.perf_counter()
    chunks = [ids[i::args.workers] for i in range(args.workers)]
    total: Counter = Counter()
    with ThreadPoolExecutor(args.workers) as pool:
        for stats in pool.map(lambda chunk: _worker(chunk, settings), chunks):
            total.update(stats)
    print(f"{len(ids)} pacientes: {dict(total)} ({time.perf_counter() - start:.1f} s)")
    return 1 if total.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
