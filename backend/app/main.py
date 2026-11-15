"""Cardia Core Backend API (bloque 5 de la arquitectura).

Arranque:  uv run uvicorn app.main:app --reload   (desde backend/)
Docs:      http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import db
from .clinical_config import ClinicalConfigError, ClinicalConfigStore
from .deps import Conn
from .routers import config, documents, ml, patients
from .settings import get_settings

log = logging.getLogger("cardia")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = ClinicalConfigStore(settings.indicators_path, settings.rules_path)
    cfg = store.get()  # falla al arrancar si la configuración no es válida
    app.state.clinical_config = store
    pool = db.open_pool(settings.database_url)
    with pool.connection() as conn:
        db_codes = {r["code"] for r in conn.execute("SELECT code FROM indicator")}
    missing = sorted({r["field"] for r in cfg.enabled_rules} - db_codes)
    if missing:
        log.warning("Reglas sobre indicadores que no existen en la base de datos: %s", missing)
    log.info("Configuración clínica %s cargada", cfg.rules_version)
    yield
    db.close_pool()


app = FastAPI(
    title="Cardia Core Backend API",
    version="0.1.0",
    description="Orquestador entre base de datos, motor de reglas (rules.json) y servicios de ML.",
    lifespan=lifespan,
)

# El listado completo con mediciones pesa varios MB en JSON; comprimido, una fracción.
app.add_middleware(GZipMiddleware, minimum_size=1_000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ClinicalConfigError)
async def config_error(_: Request, exc: ClinicalConfigError):
    return JSONResponse(status_code=500, content={"detail": f"Configuración clínica inválida: {exc}"})


API_PREFIX = "/api/v1"
app.include_router(patients.router, prefix=API_PREFIX)
app.include_router(config.router, prefix=API_PREFIX)
app.include_router(ml.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)


@app.get(API_PREFIX + "/health", tags=["sistema"])
def health(conn: Conn):
    conn.execute("SELECT 1")
    return {"status": "ok"}
