"""Configuración clínica compartida: el frontend puede leerla del backend en lugar de del disco."""
from fastapi import APIRouter

from ..deps import Config
from ..patients_service import CONDITION_RULES

router = APIRouter(prefix="/config", tags=["configuración"])


@router.get("/rules")
def rules(config: Config):
    return {**config.rules, "rulesVersion": config.rules_version}


@router.get("/indicators")
def indicators(config: Config):
    return config.indicators


@router.get("/conditions")
def conditions():
    """Cómo se deriva cada etiqueta de antecedentes del listado."""
    return [{"label": k, "rule": v} for k, v in CONDITION_RULES.items()]
