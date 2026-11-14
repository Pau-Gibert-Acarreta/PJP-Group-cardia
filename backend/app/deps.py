"""Dependencias compartidas de FastAPI."""
from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path, Request
from psycopg import Connection

from . import patients_service
from .clinical_config import ClinicalConfig
from .db import get_conn
from .settings import Settings, get_settings

Conn = Annotated[Connection, Depends(get_conn)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def clinical_config(request: Request) -> ClinicalConfig:
    return request.app.state.clinical_config.get()


Config = Annotated[ClinicalConfig, Depends(clinical_config)]


def clinician(settings: AppSettings,
              x_clinician: Annotated[str | None, Header(max_length=200)] = None) -> str:
    """Autor de notas y ajustes. Provisional hasta que exista autenticación real."""
    return (x_clinician or "").strip() or settings.default_clinician


Clinician = Annotated[str, Depends(clinician)]


def existing_patient(conn: Conn, patient_id: Annotated[int, Path(description="RANDID del paciente")]) -> int:
    if not patients_service.exists(conn, patient_id):
        raise HTTPException(404, f"Paciente {patient_id} no encontrado")
    return patient_id


PatientId = Annotated[int, Depends(existing_patient)]


def require_ml_key(settings: AppSettings,
                   x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Los endpoints /ml son para los servicios de ML, no para el navegador."""
    if not settings.ml_api_key:
        raise HTTPException(503, "API de ML desactivada: define CARDIA_ML_API_KEY")
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.ml_api_key):
        raise HTTPException(401, "X-API-Key inválida")
