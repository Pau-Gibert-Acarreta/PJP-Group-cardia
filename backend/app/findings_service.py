"""Evalúa las reglas sobre la base de datos y mantiene la tabla `finding`.

Un hallazgo queda activo mientras su regla se cumpla con las dos últimas
mediciones. Si deja de cumplirse, la regla se desactiva o cambian las
mediciones comparadas, el hallazgo anterior se cierra (resolved_at) y, si
procede, se abre uno nuevo. La tabla conserva así el historial completo.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from psycopg import Connection

from .clinical_config import ClinicalConfig
from .formatting import iso
from .rules_engine import Point, evaluate


@dataclass
class RefreshStats:
    patients: int = 0
    created: int = 0
    resolved: int = 0
    active: int = 0
    relabeled: int = 0   # activos cuyo título o gravedad se actualizó por un cambio en las reglas


def _load_points(conn: Connection, fields: list[str], patient_ids: list[int] | None):
    sql = """
        SELECT m.patient_id, m.indicator_code, m.measured_at, m.value, i.unit
        FROM measurement m JOIN indicator i ON i.code = m.indicator_code
        WHERE m.indicator_code = ANY(%(fields)s)
    """
    params: dict = {"fields": fields}
    if patient_ids is not None:
        sql += " AND m.patient_id = ANY(%(ids)s)"
        params["ids"] = patient_ids
    points: dict[int, dict[str, list[Point]]] = defaultdict(lambda: defaultdict(list))
    for row in conn.execute(sql, params):
        points[row["patient_id"]][row["indicator_code"]].append(
            Point(row["value"], row["measured_at"], row["unit"]))
    return points


def refresh(conn: Connection, config: ClinicalConfig, patient_ids: list[int] | None = None) -> RefreshStats:
    """Recalcula los hallazgos de los pacientes indicados (todos si es None)."""
    rules = config.enabled_rules
    fields = sorted({r["field"] for r in rules})
    points = _load_points(conn, fields, patient_ids)

    if patient_ids is None:
        patient_ids = [r["patient_id"] for r in conn.execute("SELECT patient_id FROM patient")]

    active_sql = "SELECT * FROM finding WHERE resolved_at IS NULL AND patient_id = ANY(%s)"
    active = {(r["patient_id"], r["rule_id"]): r for r in conn.execute(active_sql, [patient_ids])}

    to_resolve: list[tuple] = []
    to_insert: list[dict] = []
    to_relabel: list[tuple] = []
    keep: set[tuple] = set()
    stats = RefreshStats(patients=len(patient_ids))

    for pid in patient_ids:
        for f in evaluate(points.get(pid, {}), config.indicator_by_field, rules):
            key = (pid, f.rule["id"])
            current = active.get(key)
            s = f.summary
            if current and current["current_at"] == s.latest.at and current["previous_at"] == s.previous.at:
                # Mismo hallazgo. Si la regla cambió de título o gravedad, se actualiza en el sitio.
                if (current["title"], current["severity"], current["rules_version"]) != (
                        f.rule["title"], f.rule["severity"], config.rules_version):
                    to_relabel.append((f.rule["title"], f.rule["severity"], config.rules_version,
                                       current["finding_id"]))
                keep.add(key)
                continue
            if current:
                to_resolve.append((current["finding_id"],))
            to_insert.append({
                "patient_id": pid, "rule_id": f.rule["id"], "rules_version": config.rules_version,
                "indicator_code": f.rule["field"], "severity": f.rule["severity"], "title": f.rule["title"],
                "current_value": s.latest.value, "current_at": s.latest.at,
                "previous_value": s.previous.value, "previous_at": s.previous.at,
            })
            keep.add(key)

    # Activos que ya no se cumplen (o cuya regla se ha desactivado o borrado).
    to_resolve += [(row["finding_id"],) for key, row in active.items() if key not in keep]

    with conn.cursor() as cur:
        if to_resolve:
            cur.executemany("UPDATE finding SET resolved_at = now() WHERE finding_id = %s", to_resolve)
        if to_relabel:
            cur.executemany("UPDATE finding SET title = %s, severity = %s, rules_version = %s "
                            "WHERE finding_id = %s", to_relabel)
        if to_insert:
            cur.executemany("""
                INSERT INTO finding (patient_id, rule_id, rules_version, indicator_code, severity, title,
                                     current_value, current_at, previous_value, previous_at)
                VALUES (%(patient_id)s, %(rule_id)s, %(rules_version)s, %(indicator_code)s, %(severity)s,
                        %(title)s, %(current_value)s, %(current_at)s, %(previous_value)s, %(previous_at)s)
            """, to_insert)

    stats.created, stats.resolved, stats.active = len(to_insert), len(to_resolve), len(keep)
    stats.relabeled = len(to_relabel)
    return stats


def serialize(row: dict, config: ClinicalConfig) -> dict:
    ind = config.indicator_by_field.get(row["indicator_code"], {})
    delta = float(f"{row['current_value'] - row['previous_value']:.12g}")
    pct = (float(f"{delta / abs(row['previous_value']) * 100:.12g}")
           if row["previous_value"] != 0 else None)
    return {
        "id": str(row["finding_id"]),
        "ruleId": row["rule_id"],
        "rulesVersion": row["rules_version"],
        "field": row["indicator_code"],
        "label": ind.get("label"),
        "unit": ind.get("unit"),
        "title": row["title"],
        "severity": row["severity"],
        "current": {"value": row["current_value"], "date": iso(row["current_at"])},
        "previous": {"value": row["previous_value"], "date": iso(row["previous_at"])},
        "delta": delta,
        "percentChange": pct,
        "intervalDays": round((row["current_at"] - row["previous_at"]).total_seconds() / 86400, 2),
        "detectedAt": iso(row["detected_at"]),
        "resolvedAt": iso(row["resolved_at"]),
    }


def active_for(conn: Connection, patient_id: int, config: ClinicalConfig) -> list[dict]:
    # Mismo orden que las reglas en el JSON, como en el frontend.
    order = {r["id"]: i for i, r in enumerate(config.rules["rules"])}
    rows = conn.execute(
        "SELECT * FROM finding WHERE patient_id = %s AND resolved_at IS NULL", [patient_id]).fetchall()
    rows.sort(key=lambda r: order.get(r["rule_id"], len(order)))
    return [serialize(r, config) for r in rows]
