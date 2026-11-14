"""Cuerpos de las peticiones (validados por Pydantic)."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class FollowupIn(BaseModel):
    followup: bool


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La nota no puede estar vacía")
        return v.strip()


class RiskClassificationIn(BaseModel):
    level: Literal["high", "medium", "low"]
    reason: str = Field(default="", max_length=2_000)


class NewTestIn(BaseModel):
    """Evento "Nueva prueba" del diagrama: llegan resultados nuevos de un paciente."""
    takenAt: datetime | None = Field(default=None, description="Momento de la prueba; por defecto, ahora")
    source: Literal["lab", "exam", "document", "manual"] = "lab"
    values: dict[str, float] = Field(min_length=1, description="{ field: valor } en la unidad del indicador")
    documentId: UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    recalculateRisk: bool = True

    @field_validator("values")
    @classmethod
    def finite(cls, v: dict[str, float]) -> dict[str, float]:
        bad = [k for k, x in v.items() if not math.isfinite(x)]
        if bad:
            raise ValueError(f"Valores no finitos: {', '.join(bad)}")
        return v


class PredictionIn(BaseModel):
    """Lo que el Motor de Riesgo (4B) envía al guardar una predicción por su cuenta."""
    target: Literal["cv", "diabetes", "renal"] = "cv"
    probability: float = Field(ge=0, le=1)
    modelName: str
    modelVersion: str
    horizonYears: int = Field(gt=0)
    inputExamTime: datetime | None = None
    trigger: Literal["new_test", "backfill", "model_promotion", "manual"] = "backfill"
    features: dict
    shapBaseValue: float | None = None
    shapTopK: list[dict] = []


class EmbeddingItem(BaseModel):
    patientId: int
    examTime: datetime
    embedding: list[float] = Field(min_length=16, max_length=16)


class EmbeddingsIn(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    items: list[EmbeddingItem] = Field(min_length=1, max_length=5_000)


class EmbeddingSearchIn(BaseModel):
    version: str
    embedding: list[float] = Field(min_length=16, max_length=16)
    k: int = Field(default=20, ge=1, le=200)
    excludePatientId: int | None = None
