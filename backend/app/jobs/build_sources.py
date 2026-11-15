"""Construye las fuentes de datos separadas por origen (se ejecuta una sola vez).

    uv run python -m app.jobs.build_sources                 # data/raw.csv -> data/sources/
    uv run python -m app.jobs.build_sources --raw otra/ruta/raw.csv --out otra/carpeta

Detalle de cada fuente en app/etl/sources.py. Después: python -m app.jobs.load_sources --reset
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from ..etl.sources import build
from ..settings import REPO_ROOT

RAW = REPO_ROOT / "data" / "raw.csv"
SOURCES = REPO_ROOT / "data" / "sources"


def main() -> int:
    parser = argparse.ArgumentParser(description="Separa raw.csv en fuentes por origen y genera los datos sintéticos")
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--out", type=Path, default=SOURCES)
    args = parser.parse_args()
    if not args.raw.exists():
        parser.error(f"No se encuentra {args.raw} (no está en git: cópialo en data/)")
    start = time.perf_counter()
    counts = build(args.raw, args.out)
    for name, rows in counts.items():
        print(f"  {name:<24} {rows:>7} filas")
    print(f"Fuentes en {args.out} ({time.perf_counter() - start:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
