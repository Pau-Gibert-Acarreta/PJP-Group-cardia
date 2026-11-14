"""Configuración por variables de entorno (prefijo CARDIA_)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CARDIA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:cardia@localhost:5432/cardia"

    # Configuración clínica compartida (bloque 3 "Volúmenes compartidos" del diagrama).
    # Por defecto, los mismos JSON que ya usa el frontend: una sola fuente de verdad.
    rules_path: Path = REPO_ROOT / "src" / "config" / "finding-rules.json"
    indicators_path: Path = REPO_ROOT / "src" / "config" / "indicators.json"

    # Microservicio 4B (Motor de Riesgo + XAI). Sin URL, el backend no calcula riesgo.
    ml_risk_url: str | None = None
    ml_timeout_seconds: float = 10.0
    risk_targets: list[str] = ["cv"]

    # Clave que deben enviar los servicios de ML en la cabecera X-API-Key.
    # Sin clave configurada, los endpoints /api/v1/ml quedan desactivados.
    ml_api_key: str | None = None

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Autor por defecto de notas y ajustes mientras no haya autenticación.
    # El frontend puede enviar la cabecera X-Clinician para indicar otro.
    default_clinician: str = "Dra. Carmen Vidal"


@lru_cache
def get_settings() -> Settings:
    return Settings()
