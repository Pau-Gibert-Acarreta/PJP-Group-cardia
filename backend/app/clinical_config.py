"""Carga y validación de la configuración clínica compartida con el frontend.

- indicators.json: definición de cada indicador (field, unidad, decimales...).
- finding-rules.json (rules.json en el diagrama): reglas de hallazgos.

La validación replica src/domain/clinical-config.js para que un JSON que
acepta el frontend lo acepte también el backend, y al revés. Los archivos se
releen cuando cambian en disco, así que editar las reglas no exige reiniciar.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONDITION_METRICS = {"current", "previous", "delta", "percent_change"}
OPERATORS = {"gt", "gte", "lt", "lte", "eq"}
SEVERITIES = {"attention", "warning"}


class ClinicalConfigError(ValueError):
    pass


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(config: dict, rule_config: dict) -> None:
    if not isinstance(config.get("indicators"), list) or not isinstance(rule_config.get("rules"), list):
        raise ClinicalConfigError("La configuración debe incluir indicators y rules.")
    fields: set[str] = set()
    for ind in config["indicators"]:
        field = ind.get("field")
        decimals = ind.get("decimals")
        if (not isinstance(field, str) or not field.strip() or field in fields
                or not isinstance(ind.get("label"), str) or not isinstance(ind.get("unit"), str)
                or not isinstance(decimals, int) or isinstance(decimals, bool) or not 0 <= decimals <= 6):
            raise ClinicalConfigError("Definición de indicador inválida o duplicada.")
        fields.add(field)
    kdigo = config.get("kdigoFields") or {}
    if (not isinstance(config.get("overviewFields"), list)
            or any(f not in fields for f in config["overviewFields"])
            or kdigo.get("egfr") not in fields or kdigo.get("acr") not in fields):
        raise ClinicalConfigError("Campos de resumen o KDIGO desconocidos.")
    ids: set[str] = set()
    for rule in rule_config["rules"]:
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id or rule_id in ids:
            raise ClinicalConfigError("Identificador de regla inválido o duplicado.")
        ids.add(rule_id)
        if rule.get("enabled") is False:
            continue
        max_days = rule.get("maxIntervalDays")
        if (rule.get("field") not in fields
                or not isinstance(rule.get("title"), str) or not rule["title"].strip()
                or rule.get("severity") not in SEVERITIES
                or not isinstance(rule.get("conditions"), list) or not rule["conditions"]
                or (max_days is not None and (not _is_number(max_days) or max_days <= 0))):
            raise ClinicalConfigError(f"Regla inválida: {rule_id}")
        for cond in rule["conditions"]:
            if (cond.get("metric") not in CONDITION_METRICS or cond.get("operator") not in OPERATORS
                    or not _is_number(cond.get("value"))):
                raise ClinicalConfigError(f"Condición inválida: {rule_id}")


@dataclass(frozen=True)
class ClinicalConfig:
    indicators: dict          # contenido de indicators.json
    rules: dict               # contenido de finding-rules.json
    rules_version: str        # "v<version>-<sha256 corto>": se guarda en cada hallazgo

    @property
    def indicator_by_field(self) -> dict[str, dict]:
        return {ind["field"]: ind for ind in self.indicators["indicators"]}

    @property
    def enabled_rules(self) -> list[dict]:
        return [r for r in self.rules["rules"] if r.get("enabled") is not False]


def load(indicators_path: Path, rules_path: Path) -> ClinicalConfig:
    raw_rules = rules_path.read_bytes()
    indicators = json.loads(indicators_path.read_text(encoding="utf-8"))
    rules = json.loads(raw_rules.decode("utf-8"))
    validate(indicators, rules)
    digest = hashlib.sha256(raw_rules).hexdigest()[:12]
    return ClinicalConfig(indicators, rules, f"v{rules.get('version', 0)}-{digest}")


class ClinicalConfigStore:
    """Mantiene la última configuración válida y la recarga si cambian los archivos."""

    def __init__(self, indicators_path: Path, rules_path: Path):
        self._paths = (indicators_path, rules_path)
        self._lock = threading.Lock()
        self._mtimes: tuple[float, float] | None = None
        self._config: ClinicalConfig | None = None

    def get(self) -> ClinicalConfig:
        mtimes = tuple(p.stat().st_mtime for p in self._paths)
        with self._lock:
            if self._config is None or mtimes != self._mtimes:
                # Si el JSON nuevo es inválido se lanza la excepción: mejor un
                # error visible que evaluar reglas que nadie ha validado.
                self._config = load(*self._paths)
                self._mtimes = mtimes
            return self._config
