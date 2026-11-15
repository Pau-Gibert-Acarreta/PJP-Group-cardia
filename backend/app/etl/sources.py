"""Construye las fuentes de datos separadas por origen (se ejecuta una sola vez).

Parte de data/raw.csv (Framingham) y genera los datos sintéticos que el dataset no tiene.
Cada fuente imita el sistema del que vendría en un centro real:

    ehr_patients.csv      Historia clínica: datos del paciente + identidad sintética
    ehr_visits.csv        Historia clínica: cuestionario y estado en cada visita
    data_pressure.csv     Monitor de constantes (ancho): PA, frecuencia cardíaca, IMC
    data_blood.csv        Laboratorio, sangre (largo, LOINC): glucosa, lípidos + HbA1c y creatinina sintéticas
    data_urine.csv        Laboratorio, orina (largo, LOINC): cociente albúmina/creatinina sintético
    registry_outcomes.csv Registro de seguimiento: eventos a 24 años (etiquetas de entrenamiento)

Las fuentes conservan los códigos del estudio (sexo 1/2, flags 0/1) y el día de estudio
(TIME): las transformaciones a la forma de la base de datos las hace el ETL (load.py).

Datos sintéticos: misma lógica que el antiguo db/004_synthetic_fill.sql, que este módulo sustituye
(la carga reproduce exactamente la base de datos que generaba).
Son deterministas: cada valor sale de md5(patient_id + clave), así que regenerar las
fuentes da exactamente lo mismo.
"""
from __future__ import annotations

import csv
import hashlib
import math
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

LOINC = {  # código LOINC -> (nombre en el laboratorio, unidad)
    "2345-7": ("Glucose [Mass/volume] in Serum or Plasma", "mg/dL"),
    "2093-3": ("Cholesterol [Mass/volume] in Serum or Plasma", "mg/dL"),
    "2085-9": ("Cholesterol in HDL [Mass/volume] in Serum or Plasma", "mg/dL"),
    "13457-7": ("Cholesterol in LDL [Mass/volume] in Serum or Plasma by calculation", "mg/dL"),
    "4548-4": ("Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "2160-0": ("Creatinine [Mass/volume] in Serum or Plasma", "mg/dL"),
    "9318-7": ("Albumin/Creatinine [Mass Ratio] in Urine", "mg/g"),
}

# ---------------------------------------------------------------- aleatoriedad determinista

def u(key: str) -> float:
    """Número en [0, 1) estable para cada clave (igual que pg_temp.u en el antiguo 004)."""
    return int(hashlib.md5(key.encode()).hexdigest()[:8], 16) / 4294967296.0


def n(key: str) -> float:
    """Normal estándar determinista (Box-Muller)."""
    return math.sqrt(-2 * math.log(max(u(key + ":a"), 1e-9))) * math.cos(2 * math.pi * u(key + ":b"))


def pick(options: list[str], key: str) -> str:
    return options[math.floor(u(key) * len(options))]


def rnd(value: float, decimals: int) -> float:
    """Redondeo "hacia fuera" en el .5, como round(numeric) de PostgreSQL."""
    return float(Decimal(repr(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------- identidad sintética

MALE = ['Antonio', 'José', 'Manuel', 'Francisco', 'David', 'Juan', 'Javier', 'Daniel', 'José Luis', 'Carlos',
        'Jesús', 'Alejandro', 'Miguel', 'Rafael', 'Pedro', 'Ángel', 'Pablo', 'Sergio', 'Fernando', 'Jorge',
        'Luis', 'Alberto', 'Álvaro', 'Diego', 'Adrián', 'Raúl', 'Enrique', 'Ramón', 'Vicente', 'Andrés',
        'Joaquín', 'Santiago', 'Víctor', 'Eduardo', 'Roberto', 'Jaime', 'Ignacio', 'Alfonso', 'Ricardo', 'Emilio',
        'Jordi', 'Marc', 'Pau', 'Xavier', 'Iñaki']
FEMALE = ['María', 'Carmen', 'Ana', 'Isabel', 'Laura', 'Pilar', 'Dolores', 'Cristina', 'Marta', 'Lucía',
          'Elena', 'Rosa', 'Francisca', 'Antonia', 'Mercedes', 'Paula', 'Raquel', 'Teresa', 'Sara', 'Patricia',
          'Rocío', 'Beatriz', 'Encarnación', 'Julia', 'Silvia', 'Montserrat', 'Nuria', 'Irene', 'Alicia', 'Inmaculada',
          'Rosario', 'Concepción', 'Sonia', 'Eva', 'Andrea', 'Esther', 'Victoria', 'Ángela', 'Natalia', 'Margarita',
          'Núria', 'Laia', 'Mireia', 'Ainhoa', 'Begoña']
SURNAMES = ['García', 'Rodríguez', 'González', 'Fernández', 'López', 'Martínez', 'Sánchez', 'Pérez', 'Gómez', 'Martín',
            'Jiménez', 'Ruiz', 'Hernández', 'Díaz', 'Moreno', 'Muñoz', 'Álvarez', 'Romero', 'Alonso', 'Gutiérrez',
            'Navarro', 'Torres', 'Domínguez', 'Vázquez', 'Ramos', 'Gil', 'Ramírez', 'Serrano', 'Blanco', 'Molina',
            'Morales', 'Suárez', 'Ortega', 'Delgado', 'Castro', 'Ortiz', 'Rubio', 'Marín', 'Sanz', 'Núñez',
            'Iglesias', 'Medina', 'Garrido', 'Cortés', 'Castillo', 'Santos', 'Lozano', 'Guerrero', 'Cano', 'Prieto',
            'Méndez', 'Cruz', 'Calvo', 'Gallego', 'Vidal', 'León', 'Márquez', 'Herrera', 'Peña', 'Flores',
            'Cabrera', 'Campos', 'Vega', 'Fuentes', 'Carrasco', 'Diez', 'Caballero', 'Reyes', 'Nieto', 'Aguilar',
            'Puig', 'Ferrer', 'Soler', 'Pujol', 'Vila', 'Etxeberria', 'Costa', 'Pascual', 'Santana', 'Herrero']
_ACCENTS = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")


def identity(patient_id: int, sex_code: str) -> dict:
    """Nombre, CIP, teléfono y email ficticios (example.test es un dominio reservado)."""
    pid = str(patient_id)
    first = pick(MALE if sex_code == "1" else FEMALE, pid + ":first")
    s1, s2 = pick(SURNAMES, pid + ":s1"), pick(SURNAMES, pid + ":s2")
    phone = (f"6{math.floor(u(pid + ':ph1') * 100):02d} {math.floor(u(pid + ':ph2') * 1000):03d} "
             f"{math.floor(u(pid + ':ph3') * 1000):03d}")
    email = (f"{first.replace(' ', '').translate(_ACCENTS).lower()}.{s1.translate(_ACCENTS).lower()}"
             f".{pid}@example.test")
    return {"first_name": first, "last_name": f"{s1} {s2}", "cip": f"SYN{patient_id:07d}",
            "phone": phone, "email": email}


# ---------------------------------------------------------------- analíticas sintéticas

def synthetic_labs(patient_id: int, period: int, sex_code: str, age: float, diabetes: bool,
                   prev_hypertension: bool, glucose: float | None, systolic: float | None) -> dict:
    """HbA1c (%), creatinina (mg/dL) y ACR (mg/g) de una visita. El eGFR lo calcula el ETL.

    - HbA1c: diabético, a partir de la glucosa (ADAG) y >= 6,5; si no, ~5,3 según glucosa y edad.
    - Creatinina: base por sexo, sube con la edad, la hipertensión y la diabetes.
    - ACR: log-normal alrededor de 8 mg/g, mayor con diabetes, hipertensión y PAS >= 140.
    Cada paciente tiene un desplazamiento propio (pk) y cada visita una variación menor (ek).
    """
    pk, ek = str(patient_id), f"{patient_id}:{period}"
    if diabetes and glucose is not None:
        base = max(6.5, (min(glucose, 400) + 46.7) / 28.7 + 0.3)
    elif diabetes:
        base = 7.4
    else:
        base = min(6.4, 5.3 + 0.008 * ((glucose if glucose is not None else 80) - 80) + 0.008 * max(age - 45, 0))
    hba1c = min(14, max(4.0, base + 0.25 * n(pk + ":a1c") + 0.15 * n(ek + ":a1c")))
    creatinine = min(6, max(0.4, (0.95 if sex_code == "1" else 0.75) * (1 + 0.006 * max(age - 40, 0))
                            + (0.08 if prev_hypertension else 0) + (0.12 if diabetes else 0)
                            + 0.12 * n(pk + ":cr") + 0.05 * n(ek + ":cr")))
    acr = min(3000, max(1, 8 * math.exp(0.6 * n(pk + ":acr") + 0.3 * n(ek + ":acr"))
                         * (2.5 if diabetes else 1) * (1.8 if prev_hypertension else 1)
                         * (1.4 if (systolic or 0) >= 140 else 1)))
    return {"hba1c": rnd(hba1c, 1), "creatinine": rnd(creatinine, 2), "acr": rnd(acr, 0)}


# ---------------------------------------------------------------- construcción de las fuentes

def _num(text: str) -> float | None:
    text = (text or "").strip()
    return None if text in ("", "NA") else float(text)


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if float(value).is_integer() else repr(value)


def build(raw_csv: Path, out: Path) -> dict[str, int]:
    """Escribe las seis fuentes en `out` y devuelve cuántas filas tiene cada una."""
    with open(raw_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: (int(r["RANDID"]), int(r["PERIOD"])))
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    def write(name: str, header: list[str], records: list[list]):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(records)
        counts[name] = len(records)

    first_visit = {}
    for r in rows:
        first_visit.setdefault(r["RANDID"], r)

    write("ehr_patients.csv",
          ["patient_id", "sex", "education", "first_name", "last_name", "cip", "phone", "email"],
          [[pid, r["SEX"], r["educ"], *identity(int(pid), r["SEX"]).values()] for pid, r in first_visit.items()])

    flags = ["CURSMOKE", "CIGPDAY", "BPMEDS", "DIABETES", "PREVCHD", "PREVAP", "PREVMI", "PREVSTRK", "PREVHYP"]
    write("ehr_visits.csv",
          ["patient_id", "visit", "study_day", "age"] + [f.lower() for f in flags],
          [[r["RANDID"], r["PERIOD"], r["TIME"], r["AGE"]] + [_fmt(_num(r[f])) for f in flags] for r in rows])

    vitals = [("SYSBP", "systolic_mmhg"), ("DIABP", "diastolic_mmhg"), ("HEARTRTE", "heart_rate_bpm"), ("BMI", "bmi_kg_m2")]
    write("data_pressure.csv", ["patient_id", "study_day"] + [c for _, c in vitals],
          [[r["RANDID"], r["TIME"]] + [_fmt(_num(r[k])) for k, _ in vitals]
           for r in rows if any(_num(r[k]) is not None for k, _ in vitals)])

    blood, urine = [], []
    for r in rows:
        pid, period = int(r["RANDID"]), int(r["PERIOD"])
        labs = synthetic_labs(pid, period, r["SEX"], float(r["AGE"]), r["DIABETES"] == "1", r["PREVHYP"] == "1",
                              _num(r["GLUCOSE"]), _num(r["SYSBP"]))
        results = [("2345-7", _num(r["GLUCOSE"])), ("2093-3", _num(r["TOTCHOL"])), ("2085-9", _num(r["HDLC"])),
                   ("13457-7", _num(r["LDLC"])), ("4548-4", labs["hba1c"]), ("2160-0", labs["creatinine"])]
        for code, value in results:
            if value is not None:
                blood.append([r["RANDID"], r["TIME"], code, LOINC[code][0], _fmt(value), LOINC[code][1]])
        urine.append([r["RANDID"], r["TIME"], "9318-7", LOINC["9318-7"][0], _fmt(labs["acr"]), "mg/g"])
    lab_header = ["patient_id", "study_day", "loinc", "test_name", "value", "unit"]
    write("data_blood.csv", lab_header, blood)
    write("data_urine.csv", lab_header, urine)

    outcomes = ["DEATH", "ANGINA", "HOSPMI", "MI_FCHD", "ANYCHD", "STROKE", "CVD", "HYPERTEN",
                "TIMEDTH", "TIMEAP", "TIMEMI", "TIMEMIFC", "TIMECHD", "TIMESTRK", "TIMECVD", "TIMEHYP"]
    write("registry_outcomes.csv", ["patient_id"] + [o.lower() for o in outcomes],
          [[pid] + [r[o] for o in outcomes] for pid, r in first_visit.items()])
    return counts
