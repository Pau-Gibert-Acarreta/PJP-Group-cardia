"""Cardia: puesta en marcha completa con un solo comando.

Se lanza con setup.cmd / setup.ps1 (Windows) o setup.sh (macOS/Linux), que instalan uv si
falta y ejecutan este script con el Python que trae uv. Solo usa la biblioteca estándar.

Pasos (cada uno se salta si ya está hecho, así que volver a ejecutarlo es rápido y seguro):
  1. Comprueba requisitos: Docker (lo arranca si está parado), Node.js >= 20 y data/raw.csv.
  2. Instala las dependencias de Python (backend/ y ml/) con uv.
  3. Base de datos: crea y arranca el contenedor PostgreSQL + TimescaleDB + pgvector.
  4. Datos: fuentes desde raw.csv, carga con el ETL, hallazgos e índice KNN.
  5. Servicios: Motor de Riesgo (ML), backend y frontend.
  6. Predicción de riesgo de todo el cupo y analíticas PDF (en paralelo).
  7. Deja todo en marcha hasta Ctrl+C (o termina con --no-serve).

Opciones:  --reset (recarga la base de datos desde cero)   --skip-pdfs   --no-serve   --check
           --db-port 5432 --api-port 8000 --ml-port 8001 --web-port 5173 --db-container cardia-db
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND, ML, DATA = ROOT / "backend", ROOT / "ml", ROOT / "data"
LOGS = ROOT / "logs"
IS_WINDOWS = platform.system() == "Windows"
DB_IMAGE = "timescale/timescaledb-ha:pg16"
DB_PASSWORD = "cardia"          # solo para el entorno local de desarrollo
EXPECTED_PATIENTS = 4434
EXPECTED_EXAMS = 11627

_started: list[subprocess.Popen] = []


# ---------------------------------------------------------------- salida

def step(n: int, total: int, text: str) -> None:
    print(f"\n[{n}/{total}] {text}", flush=True)


def info(text: str) -> None:
    print(f"      {text}", flush=True)


def fail(text: str, hint: str | None = None) -> None:
    print(f"\n  ✗ {text}", flush=True)
    if hint:
        print(f"    {hint}", flush=True)
    stop_services()
    sys.exit(1)


# ---------------------------------------------------------------- utilidades

def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None, check: bool = True,
        capture: bool = False, log: Path | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(f"\n$ {' '.join(cmd)}\n")
            result = subprocess.run(cmd, cwd=cwd, env=full_env, stdout=fh, stderr=subprocess.STDOUT, text=True)
    else:
        result = subprocess.run(cmd, cwd=cwd, env=full_env, text=True, encoding="utf-8", errors="replace",
                                capture_output=capture)
    if check and result.returncode != 0:
        detail = f" (detalle en {log.relative_to(ROOT)})" if log else ""
        output = (result.stderr or result.stdout or "").strip()[-800:] if capture else ""
        fail(f"Falló: {' '.join(cmd)}{detail}", output or None)
    return result


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:  # noqa: BLE001
        return False


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_for(check, what: str, timeout: float) -> None:
    start = time.time()
    while time.time() - start < timeout:
        if check():
            return
        time.sleep(1.5)
    fail(f"{what} no ha respondido en {int(timeout)} s")


def psql(container: str, sql: str) -> str:
    result = run(["docker", "exec", container, "psql", "-U", "postgres", "-d", "cardia", "-Atc", sql],
                 capture=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


# ---------------------------------------------------------------- 1. requisitos

def check_requirements() -> None:
    raw = DATA / "raw.csv"
    if not raw.exists():
        fail("Falta data/raw.csv (el dataset de Framingham; no está en git).",
             "Cópialo en data/raw.csv y vuelve a ejecutar el script.")
    info("data/raw.csv ✓")

    node = shutil.which("node")
    if not node:
        fail("No se encuentra Node.js (>= 20).",
             "Instálalo desde https://nodejs.org" + (" o con: winget install OpenJS.NodeJS.LTS" if IS_WINDOWS else ""))
    version = run([node, "--version"], capture=True).stdout.strip()
    if int(version.lstrip("v").split(".")[0]) < 20:
        fail(f"Node.js {version} es demasiado antiguo: hace falta la 20 o posterior.")
    info(f"Node.js {version} ✓")

    if not shutil.which("docker"):
        fail("No se encuentra Docker.",
             "Instala Docker Desktop: https://www.docker.com/products/docker-desktop/"
             + (" (o: winget install Docker.DockerDesktop)" if IS_WINDOWS else ""))
    if run(["docker", "info"], capture=True, check=False).returncode != 0:
        desktop = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe"
        if IS_WINDOWS and desktop.exists():
            info("Docker está parado: arrancando Docker Desktop…")
            subprocess.Popen([str(desktop)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Darwin":
            info("Docker está parado: arrancando Docker Desktop…")
            subprocess.Popen(["open", "-a", "Docker"])
        else:
            fail("Docker está instalado pero no está en marcha.", "Arráncalo (p. ej. sudo systemctl start docker).")
        wait_for(lambda: run(["docker", "info"], capture=True, check=False).returncode == 0, "Docker", 180)
    info("Docker ✓")


# ---------------------------------------------------------------- 2. dependencias

def install_python_deps() -> None:
    for project in (BACKEND, ML):
        info(f"uv sync en {project.name}/ …")
        run(["uv", "sync", "--quiet"], cwd=project, log=LOGS / "install.log")
    info("Dependencias de Python ✓ (frontend: sin dependencias)")


# ---------------------------------------------------------------- 3. base de datos

def start_database(container: str, port: int) -> None:
    state = run(["docker", "inspect", "-f", "{{.State.Running}}", container], capture=True, check=False)
    if state.returncode != 0:
        info(f"Creando el contenedor {container} ({DB_IMAGE}; la primera vez descarga ~1 GB)…")
        if not port_free(port):
            fail(f"El puerto {port} está ocupado por otro programa.", "Usa otro con --db-port.")
        run(["docker", "run", "-d", "--name", container, "-e", f"POSTGRES_PASSWORD={DB_PASSWORD}",
             "-e", "POSTGRES_DB=cardia", "-p", f"{port}:5432",
             "-v", f"{container}-data:/home/postgres/pgdata", DB_IMAGE], log=LOGS / "database.log")
    elif state.stdout.strip() != "true":
        info(f"Arrancando el contenedor {container}…")
        run(["docker", "start", container], capture=True)
    else:
        info(f"El contenedor {container} ya está en marcha")
    # pg_isready responde antes de que termine la inicialización: se espera a una consulta real.
    wait_for(lambda: psql(container, "SELECT 1") == "1", "PostgreSQL", 180)
    info(f"PostgreSQL ✓ (localhost:{port})")


# ---------------------------------------------------------------- 4. datos

def database_loaded(container: str) -> bool:
    patients = psql(container, "SELECT count(*) FROM cardia.patient")
    schema_ok = psql(container, "SELECT 1 FROM information_schema.columns WHERE table_schema = 'cardia' "
                                "AND table_name = 'clinical_event' AND column_name = 'test_kind'") == "1"
    knn_ok = psql(container, "SELECT 1 FROM information_schema.tables WHERE table_schema = 'cardia' "
                             "AND table_name = 'embedding_model'") == "1"
    return patients == str(EXPECTED_PATIENTS) and schema_ok and knn_ok


def load_data(container: str, env: dict, reset: bool) -> None:
    sources = DATA / "sources"
    if reset or not (sources / "data_blood.csv").exists():
        info("Construyendo las fuentes desde raw.csv…")
        run(["uv", "run", "python", "-m", "app.jobs.build_sources"], cwd=BACKEND, env=env, log=LOGS / "data.log")
    if reset or not database_loaded(container):
        info("Cargando la base de datos con el ETL (vacía y recrea el esquema)…")
        run(["uv", "run", "python", "-m", "app.jobs.load_sources", "--reset"], cwd=BACKEND, env=env,
            log=LOGS / "data.log")
        info("Hallazgos (motor de reglas)…")
        run(["uv", "run", "python", "-m", "app.jobs.evaluate_findings"], cwd=BACKEND, env=env, log=LOGS / "data.log")
    else:
        info(f"La base de datos ya tiene los {EXPECTED_PATIENTS} pacientes: no se recarga (usa --reset para forzarlo)")
    if psql(container, "SELECT count(*) FROM cardia.exam_embedding WHERE embedding_version = 'knn-v1'") != str(EXPECTED_EXAMS):
        info("Índice de casos similares (KNN)…")
        run(["uv", "run", "python", "-m", "app.jobs.build_knn_index"], cwd=BACKEND, env=env, log=LOGS / "data.log")
    if not (ML / "models" / "registry.json").exists():
        fail("Falta ml/models/registry.json (el registro del modelo de riesgo).")
    info("Datos ✓")


# ---------------------------------------------------------------- 5. servicios

def start_service(name: str, cmd: list[str], cwd: Path, env: dict, health: str, port: int) -> None:
    if http_ok(health):
        info(f"{name} ya está en marcha ({health})")
        return
    if not port_free(port):
        fail(f"El puerto {port} ({name}) está ocupado por otro programa.", "Ciérralo o elige otro puerto con las opciones del script.")
    log = open(LOGS / f"{name.lower().replace(' ', '_')}.log", "a", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0
    proc = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **env}, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=flags, start_new_session=not IS_WINDOWS)
    _started.append(proc)
    wait_for(lambda: http_ok(health) or proc.poll() is not None, name, 120)
    if proc.poll() is not None:
        fail(f"{name} se ha cerrado al arrancar.", f"Mira logs/{Path(log.name).name}")
    info(f"{name} ✓ ({health.rsplit('/', 1)[0] if 'health' in health else health})")


def stop_services() -> None:
    for proc in _started:
        if proc.poll() is None:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            else:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    _started.clear()


# ---------------------------------------------------------------- 6. riesgo y PDF

def precompute(container: str, env: dict, skip_pdfs: bool) -> None:
    errors: list[str] = []

    def risk():
        missing = psql(container, "SELECT count(*) FROM cardia.patient WHERE patient_id NOT IN "
                                  "(SELECT patient_id FROM cardia.risk_prediction WHERE target = 'cv')")
        if missing == "0":
            info("Predicción de riesgo: todos los pacientes ya la tienen")
            return
        info(f"Predicción de riesgo para {missing} pacientes (la primera vez ~12 min)…")
        r = run(["uv", "run", "python", "-m", "app.jobs.backfill_risk", "--only-missing"], cwd=BACKEND,
                env=env, check=False, log=LOGS / "risk.log")
        (errors.append("predicción de riesgo (logs/risk.log)") if r.returncode else info("Predicción de riesgo ✓"))

    def pdfs():
        linked = psql(container, "SELECT count(*) FROM cardia.clinical_event WHERE test_kind = 'blood' AND document_id IS NOT NULL")
        if linked == str(EXPECTED_EXAMS):
            info("Analíticas PDF: ya están todas ingestadas")
            return
        info("Analíticas PDF: generando las que faltan e ingestando (la primera vez ~15 min)…")
        g = run(["uv", "run", "python", "-m", "app.jobs.generate_lab_reports", "--all", "--skip-existing"],
                cwd=BACKEND, env=env, check=False, log=LOGS / "pdfs.log")
        i = run(["uv", "run", "python", "-m", "app.jobs.ingest_lab_reports"], cwd=BACKEND, env=env,
                check=False, log=LOGS / "pdfs.log") if g.returncode == 0 else g
        (errors.append("analíticas PDF (logs/pdfs.log)") if i.returncode else info("Analíticas PDF ✓"))

    jobs = [threading.Thread(target=risk)] + ([] if skip_pdfs else [threading.Thread(target=pdfs)])
    for job in jobs:
        job.start()
    for job in jobs:
        job.join()
    if errors:
        fail("No se ha completado: " + ", ".join(errors))


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="Cardia: instala, configura, carga los datos y arranca todo")
    parser.add_argument("--reset", action="store_true", help="Recarga la base de datos desde cero")
    parser.add_argument("--skip-pdfs", action="store_true", help="No genera ni ingesta las analíticas PDF")
    parser.add_argument("--no-serve", action="store_true", help="Prepara todo y termina, sin dejar los servicios en marcha")
    parser.add_argument("--check", action="store_true", help="Al final, ejecuta el smoke test y las pruebas")
    parser.add_argument("--db-container", default="cardia-db")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ml-port", type=int, default=8001)
    parser.add_argument("--web-port", type=int, default=5173)
    args = parser.parse_args()

    LOGS.mkdir(exist_ok=True)
    started = time.time()
    total = 7
    print("Cardia · puesta en marcha completa")
    env = {
        "CARDIA_DATABASE_URL": f"postgresql://postgres:{DB_PASSWORD}@localhost:{args.db_port}/cardia",
        "CARDIA_ML_RISK_URL": f"http://127.0.0.1:{args.ml_port}",
        "CARDIA_API_URL": f"http://127.0.0.1:{args.api_port}",
        "PORT": str(args.web_port),
        "PYTHONUTF8": "1",
    }
    try:
        step(1, total, "Requisitos"); check_requirements()
        step(2, total, "Dependencias"); install_python_deps()
        step(3, total, "Base de datos"); start_database(args.db_container, args.db_port)
        step(4, total, "Datos"); load_data(args.db_container, env, args.reset)
        step(5, total, "Servicios")
        start_service("Motor de Riesgo", ["uv", "run", "uvicorn", "service:app", "--port", str(args.ml_port)],
                      ML, env, f"http://127.0.0.1:{args.ml_port}/health", args.ml_port)
        start_service("Backend", ["uv", "run", "uvicorn", "app.main:app", "--port", str(args.api_port)],
                      BACKEND, env, f"http://127.0.0.1:{args.api_port}/api/v1/health", args.api_port)
        start_service("Frontend", ["node", "scripts/serve.mjs"], ROOT, env,
                      f"http://127.0.0.1:{args.web_port}/", args.web_port)
        step(6, total, "Predicción de riesgo y analíticas PDF"); precompute(args.db_container, env, args.skip_pdfs)
        step(7, total, "Comprobación")
        summary = psql(args.db_container, "SELECT (SELECT count(*) FROM cardia.patient) || ' pacientes · ' || "
                       "(SELECT count(DISTINCT patient_id) FROM cardia.risk_prediction) || ' con riesgo · ' || "
                       "(SELECT count(*) FROM cardia.document) || ' PDF · ' || "
                       "(SELECT count(*) FROM cardia.finding WHERE resolved_at IS NULL) || ' hallazgos'")
        info(summary)
        if args.check:
            info("Smoke test de la base de datos…")
            with open(ROOT / "db" / "003_smoke_test.sql", encoding="utf-8") as sql:
                r = subprocess.run(["docker", "exec", "-i", args.db_container, "psql", "-U", "postgres", "-d", "cardia",
                                    "-v", "ON_ERROR_STOP=1"], stdin=sql, capture_output=True, text=True)
            info("Smoke test ✓" if r.returncode == 0 else "Smoke test ✗ " + r.stderr[-300:])
            for project, cmd in ((BACKEND, ["uv", "run", "pytest", "-q"]), (ML, ["uv", "run", "--group", "dev", "pytest", "-q"])):
                r = run(cmd, cwd=project, env=env, check=False, capture=True)
                info(f"Pruebas {project.name}: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.returncode}")
            r = run(["node", "scripts/check.mjs"], env=env, check=False, capture=True)
            info("Pruebas frontend ✓" if r.returncode == 0 else "Pruebas frontend ✗")

        minutes = (time.time() - started) / 60
        print(f"\n✓ Cardia está lista ({minutes:.1f} min): http://localhost:{args.web_port}")
        print(f"  API: http://localhost:{args.api_port}/docs · Motor de Riesgo: http://localhost:{args.ml_port}/docs · "
              f"registros en logs/")
        if args.no_serve:
            stop_services()
            return 0
        if _started:
            print("  Pulsa Ctrl+C para parar los servicios.")
            while all(p.poll() is None for p in _started):
                time.sleep(1)
            fail("Un servicio se ha cerrado inesperadamente; mira logs/.")
        return 0
    except KeyboardInterrupt:
        print("\nParando los servicios…")
        stop_services()
        return 0


if __name__ == "__main__":
    sys.exit(main())
