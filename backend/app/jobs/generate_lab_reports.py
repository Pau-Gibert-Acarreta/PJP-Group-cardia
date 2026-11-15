"""Generador de analíticas en PDF (simula los informes del laboratorio del centro).

Adaptado del script de un compañero del equipo (generar_analitica.py): se conserva su
maquetación y su simulación de las pruebas que no están en la base de datos, pero
**los datos salen de la base de datos**, que es la fuente de verdad:

- Paciente: nombre, CIP y sexo (`patient`); edad, periodo y fecha del examen (`exam`).
- Glucosa, colesterol total, HDL y LDL: valores originales de Framingham (`measurement`).
- HbA1c, creatinina, eGFR y ACR: los valores sintéticos generados en app/etl/sources.py (`measurement`).
- Hemograma, urea, iones, perfil hepático, triglicéridos y orina (salvo ACR): no existen en la
  base de datos; se simulan aquí de forma reproducible, solo para que el informe sea realista.
  La ingesta no los guarda como mediciones.

El PDF no es la fuente de ningún dato de la base de datos: es una vista impresa de ella.

Uso (desde backend/):
    uv run python -m app.jobs.generate_lab_reports 2448 6238      # pacientes concretos
    uv run python -m app.jobs.generate_lab_reports --all           # todo el cupo (~11.600 PDF)
    uv run python -m app.jobs.generate_lab_reports --all --limit 100
    uv run python -m app.jobs.generate_lab_reports --all --skip-existing   # solo los que faltan
Salida por defecto: data/landing/lab_reports/<RANDID>/ (ignorada en git).
"""
from __future__ import annotations

import argparse
import math
import random
import time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from reportlab.graphics.shapes import Drawing, PolyLine, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..settings import REPO_ROOT, get_settings

SALIDA = REPO_ROOT / "data" / "landing" / "lab_reports"

# Centro ficticio: no usar el nombre ni la dirección de un centro real en documentos generados
HOSPITAL = "Centro de Atención Primaria"
SERVICIO = "Laboratorio de análisis clínicos"
DIRECCION = "Analítica general de salud"
LABORATORIO = f"{HOSPITAL} · {SERVICIO}"
AVISO_SINTETICO = "Documento sintético generado para la demo de Cardia · datos ficticios"

# Pruebas del informe que vienen de la base de datos: clave del informe -> indicator.code
DESDE_BD = {
    "glucosa": "glucose", "colesterol_total": "total_cholesterol", "hdl": "hdl_cholesterol", "ldl": "ldl",
    "hba1c": "hba1c", "creatinina": "serum_creatinine", "egfr": "egfr", "acr": "acr",
}

# Todo el texto en negro; solo el logo lleva color
NEGRO = colors.HexColor("#111111")
SECUNDARIO = colors.HexColor("#3a3a3a")
LINEA = colors.HexColor("#b5b5b5")
LINEA_SUAVE = colors.HexColor("#dedede")
FONDO = colors.HexColor("#f2f2f2")
LOGO = colors.HexColor("#0b5f73")
FRANJA = colors.HexColor("#ffffbf")        # color de las categorías (como en los informes de laboratorio)
FRANJA_BORDE = colors.HexColor("#d9d98a")


# ---------------------------------------------------------------- lectura de datos (base de datos)

def leer_pacientes(conn, randids: list[int] | None, limit: int | None) -> list[dict]:
    """[{patient, exams: [{..., values: {indicator_code: value}}]}] ordenados por examen."""
    filtro, params = ("WHERE p.patient_id = ANY(%s)", [randids]) if randids else ("", [])
    pacientes = conn.execute(f"""
        SELECT p.patient_id, p.sex, p.cip, p.first_name, p.last_name FROM patient p {filtro}
        ORDER BY p.patient_id {'LIMIT %s' if limit else ''}
    """, params + ([limit] if limit else [])).fetchall()
    ids = [p["patient_id"] for p in pacientes]
    examenes = defaultdict(list)
    for e in conn.execute("""
            SELECT patient_id, exam_time, period, age_years FROM exam
            WHERE patient_id = ANY(%s) ORDER BY patient_id, exam_time""", [ids]):
        examenes[e["patient_id"]].append({**e, "values": {}})
    por_instante = {(e["patient_id"], e["exam_time"]): e for lista in examenes.values() for e in lista}
    for m in conn.execute("""
            SELECT patient_id, measured_at, indicator_code, value FROM measurement
            WHERE patient_id = ANY(%s) AND indicator_code = ANY(%s)""", [ids, list(DESDE_BD.values())]):
        examen = por_instante.get((m["patient_id"], m["measured_at"]))
        if examen:
            examen["values"][m["indicator_code"]] = m["value"]
    return [{"patient": p, "exams": examenes[p["patient_id"]]} for p in pacientes]


# ---------------------------------------------------------------- formato

def fmt(valor, decimales=0):
    if valor is None:
        return None
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")  # formato español


def marca(valor, minimo=None, maximo=None):
    """'Alto', 'Bajo' o '' según los valores de referencia."""
    if valor is None:
        return ""
    if maximo is not None and valor > maximo:
        return "Alto"
    if minimo is not None and valor < minimo:
        return "Bajo"
    return ""


# ---------------------------------------------------------------- estilos

E = {
    "hospital": ParagraphStyle("hospital", fontName="Helvetica-Bold", fontSize=12.5, textColor=NEGRO, leading=15),
    "servicio": ParagraphStyle("servicio", fontName="Helvetica", fontSize=9, textColor=NEGRO, leading=11.5),
    "direccion": ParagraphStyle("direccion", fontName="Helvetica", fontSize=7.5, textColor=SECUNDARIO, leading=10),
    "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=11, textColor=NEGRO, alignment=TA_RIGHT, leading=14),
    "subtitulo": ParagraphStyle("subtitulo", fontName="Helvetica", fontSize=8.5, textColor=NEGRO, alignment=TA_RIGHT, leading=11),
    "seccion": ParagraphStyle("seccion", fontName="Helvetica-Bold", fontSize=8.8, textColor=NEGRO, leading=11),
    "celda": ParagraphStyle("celda", fontName="Helvetica", fontSize=9, textColor=NEGRO, leading=11.2),
    "celda_sec": ParagraphStyle("celda_sec", fontName="Helvetica", fontSize=8.3, textColor=NEGRO, leading=10.5),
    "cabecera_tabla": ParagraphStyle("cabecera_tabla", fontName="Helvetica-Bold", fontSize=8, textColor=NEGRO, leading=10),
    "nota": ParagraphStyle("nota", fontName="Helvetica", fontSize=7.5, textColor=SECUNDARIO, leading=9.8),
}


def p(texto, estilo="celda"):
    return Paragraph(texto, E[estilo])


# ---------------------------------------------------------------- logo

def logo(tamano=17 * mm):
    """Logo ficticio: escudo redondeado con cruz sanitaria y latido."""
    d = Drawing(tamano, tamano)
    s = tamano
    d.add(Rect(0, 0, s, s, rx=s * 0.22, ry=s * 0.22, fillColor=LOGO, strokeColor=None))
    brazo, largo = s * 0.2, s * 0.62
    d.add(Rect((s - brazo) / 2, (s - largo) / 2, brazo, largo, fillColor=colors.white, strokeColor=None))
    d.add(Rect((s - largo) / 2, (s - brazo) / 2, largo, brazo, fillColor=colors.white, strokeColor=None))
    d.add(PolyLine([s * 0.12, s * 0.5, s * 0.36, s * 0.5, s * 0.43, s * 0.36, s * 0.52, s * 0.66,
                    s * 0.58, s * 0.5, s * 0.88, s * 0.5], strokeColor=LOGO, strokeWidth=s * 0.045, strokeLineJoin=1))
    return d


# ---------------------------------------------------------------- bloques del informe

def cabecera(n_peticion, fecha):
    marca_hospital = Table([[logo(), [p(HOSPITAL, "hospital"), p(SERVICIO, "servicio"), p(DIRECCION, "direccion")]]],
                           colWidths=[20 * mm, 88 * mm])
    marca_hospital.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    derecha = [p("INFORME DE RESULTADOS", "titulo"),
               p(f"Nº de petición: <b>{n_peticion}</b>", "subtitulo"),
               p(f"Fecha de extracción: <b>{fecha.strftime('%d/%m/%Y')}</b>", "subtitulo"),
               p(f"Fecha de validación: <b>{(fecha + timedelta(days=1)).strftime('%d/%m/%Y')}</b>", "subtitulo")]
    t = Table([[marca_hospital, derecha]], colWidths=[108 * mm, 72 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, NEGRO),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def datos_paciente(paciente, examen, examen_n, total_examenes):
    sexo = {"M": "Hombre", "F": "Mujer"}.get(paciente["sex"], "No registrado")
    nombre = " ".join(x for x in (paciente["first_name"], paciente["last_name"]) if x) or "No registrado"

    def par(etiqueta, valor):
        return [p(etiqueta, "celda_sec"), p(f"<b>{valor}</b>")]
    filas = [
        par("Paciente:", nombre) + par("CIP:", paciente["cip"] or "No registrado"),
        par("ID paciente:", paciente["patient_id"]) + par("Sexo:", sexo),
        par("Edad en la extracción:", f"{examen['age_years']} años") + par("Ciclo de examen:", f"Periodo {examen['period']}"),
        par("Servicio solicitante:", "Medicina de Familia") + par("Examen:", f"{examen_n} de {total_examenes} del paciente"),
    ]
    t = Table(filas, colWidths=[38 * mm, 52 * mm, 34 * mm, 56 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),
        ("BACKGROUND", (0, 0), (-1, -1), FONDO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def titulo_seccion(texto):
    """Franja de color a todo lo ancho con el nombre de la categoría."""
    t = Table([[p(texto.upper(), "seccion")]], colWidths=[180 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FRANJA),
        ("LINEBELOW", (0, 0), (-1, -1), 0.6, FRANJA_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


ESTILO_TABLA = [
    ("BACKGROUND", (0, 0), (-1, 0), FONDO),
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINEA),
    ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINEA_SUAVE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
]


def flecha(actual, anterior, decimales):
    """↑ si sube y ↓ si baja respecto a la analítica anterior (comparando el valor redondeado que se muestra)."""
    if actual is None or anterior is None:
        return ""
    a, b = round(actual, decimales), round(anterior, decimales)
    if a > b:
        return '<font name="Symbol">↑</font>'
    if a < b:
        return '<font name="Symbol">↓</font>'
    return ""


def tabla_resultados(titulo, filas):
    """filas: [(prueba, valor, decimales, unidades, referencia, fuera_de_rango, nota_prueba, valor_anterior)]"""
    datos = [[p("Prueba", "cabecera_tabla"), p("Resultado", "cabecera_tabla"),
              p("Unidades", "cabecera_tabla"), p("Valores de referencia", "cabecera_tabla")]]
    for prueba, valor, decimales, unidades, referencia, fuera, nota_prueba, anterior in filas:
        nombre = f"{prueba}<br/><font size=7.2>{nota_prueba}</font>" if nota_prueba else prueba
        if valor is None:
            resultado = p("<i>No determinado</i>", "celda_sec")
        else:
            texto = fmt(valor, decimales)
            resultado = p((f"<b>{texto}</b>" if fuera else texto) + "&nbsp;&nbsp;" + flecha(valor, anterior, decimales))
        datos.append([p(nombre), resultado, p(unidades, "celda_sec"), p(referencia, "celda_sec")])
    t = Table(datos, colWidths=[66 * mm, 30 * mm, 28 * mm, 56 * mm], repeatRows=1)
    t.setStyle(TableStyle(ESTILO_TABLA))
    return KeepTogether([titulo_seccion(titulo), Spacer(1, 1.5 * mm), t, Spacer(1, 5 * mm)])


# ---------------------------------------------------------------- contenido clínico
#
# Las pruebas de DESDE_BD se leen de la base de datos. El resto se SIMULAN como en el
# script original: valores "basales" propios de cada paciente (semilla = RANDID) y una
# pequeña variación por examen (semilla = RANDID + periodo), reproducibles entre ejecuciones.

def _rng(*partes):
    return random.Random("-".join(str(x) for x in partes))


def _basal(randid, prueba, media, desviacion, minimo, maximo):
    return min(maximo, max(minimo, _rng(randid, prueba).gauss(media, desviacion)))


def _examen(randid, periodo, prueba, basal, variacion, minimo, maximo):
    return min(maximo, max(minimo, basal + _rng(randid, periodo, prueba).gauss(0, variacion)))


def valores(paciente, examen):
    """Todos los resultados de una analítica: los de la base de datos y los simulados."""
    randid, periodo = paciente["patient_id"], examen["period"]
    mujer = paciente["sex"] == "F"
    edad = examen["age_years"] or 50
    v = {clave: examen["values"].get(codigo) for clave, codigo in DESDE_BD.items()}

    def sim(prueba, media, desviacion, minimo, maximo, variacion):
        basal = _basal(randid, prueba, media, desviacion, minimo, maximo)
        return _examen(randid, periodo, prueba, basal, variacion, minimo, maximo)

    # Hemograma (simulado)
    v["hematies"] = sim("hematies", 4.55 if mujer else 5.05, 0.3, 3.6, 6.2, 0.12)
    v["vcm"] = sim("vcm", 90, 4.5, 76, 104, 1.2)
    v["hcm"] = sim("hcm", 30, 1.5, 25, 34.5, 0.4)
    v["hemoglobina"] = v["hematies"] * v["hcm"] / 10
    v["hematocrito"] = v["hematies"] * v["vcm"] / 10
    v["leucocitos"] = sim("leucocitos", 6.8, 1.5, 3.4, 12.5, 0.8)
    v["neutrofilos"] = sim("neutrofilos", 58, 6, 40, 78, 3)
    v["linfocitos"] = min(100 - v["neutrofilos"] - 8, sim("linfocitos", 31, 5, 15, 48, 3))
    v["plaquetas"] = sim("plaquetas", 245, 50, 130, 420, 18)

    # Bioquímica (simulada salvo glucosa, HbA1c, creatinina y eGFR, que vienen de la base de datos)
    v["urea"] = sim("urea", 32 + (edad - 50) * 0.25, 7, 15, 70, 4)
    v["urico"] = sim("urico", 4.6 if mujer else 5.8, 1.0, 2.5, 9.5, 0.4)
    v["sodio"] = sim("sodio", 140, 1.8, 133, 147, 1.2)
    v["potasio"] = sim("potasio", 4.3, 0.3, 3.3, 5.6, 0.2)

    # Triglicéridos solo cuando hay perfil lipídico
    v["trigliceridos"] = sim("trigliceridos", 115, 40, 45, 320, 18) if v["colesterol_total"] is not None else None

    # Perfil hepático (simulado)
    v["got"] = sim("got", 22, 6, 10, 55, 3)
    v["gpt"] = sim("gpt", 23, 8, 8, 70, 4)
    v["ggt"] = sim("ggt", 24 if mujer else 32, 12, 8, 110, 5)
    v["fosfatasa"] = sim("fosfatasa", 75, 18, 40, 150, 6)
    v["bilirrubina"] = sim("bilirrubina", 0.6, 0.2, 0.2, 1.6, 0.08)

    # Orina: el ACR viene de la base de datos; la albúmina se deriva de él y de la creatinina en orina
    v["creatinina_orina"] = sim("creatinina_orina", 110 if mujer else 140, 35, 40, 260, 20)
    v["albumina_orina"] = v["acr"] * v["creatinina_orina"] / 1000 if v["acr"] is not None else None
    return v


def secciones(paciente, examen, anteriores):
    """Lista de (título, filas) con las pruebas de la analítica."""
    mujer = paciente["sex"] == "F"
    v = valores(paciente, examen)
    a: dict = {}
    for previo in anteriores:  # último valor conocido de cada prueba en analíticas anteriores
        a.update({k: x for k, x in valores(paciente, previo).items() if x is not None})

    def fila_prueba(nombre, clave, decimales, unidades, minimo, maximo, referencia, nota=""):
        return (nombre, v[clave], decimales, unidades, referencia, marca(v[clave], minimo, maximo) != "", nota, a.get(clave))

    hemograma = [
        fila_prueba("Hematíes", "hematies", 2, "x10<super>12</super>/L", *((4.0, 5.2, "4,00 - 5,20") if mujer else (4.5, 5.9, "4,50 - 5,90"))),
        fila_prueba("Hemoglobina", "hemoglobina", 1, "g/dL", *((12.0, 16.0, "12,0 - 16,0") if mujer else (13.5, 17.5, "13,5 - 17,5"))),
        fila_prueba("Hematocrito", "hematocrito", 1, "%", *((36, 46, "36,0 - 46,0") if mujer else (41, 53, "41,0 - 53,0"))),
        fila_prueba("Volumen corpuscular medio (VCM)", "vcm", 1, "fL", 80, 100, "80,0 - 100,0"),
        fila_prueba("Hemoglobina corpuscular media (HCM)", "hcm", 1, "pg", 27, 33, "27,0 - 33,0"),
        fila_prueba("Leucocitos", "leucocitos", 2, "x10<super>9</super>/L", 4.0, 11.0, "4,00 - 11,00"),
        fila_prueba("Neutrófilos", "neutrofilos", 1, "%", 40, 75, "40,0 - 75,0"),
        fila_prueba("Linfocitos", "linfocitos", 1, "%", 20, 45, "20,0 - 45,0"),
        fila_prueba("Plaquetas", "plaquetas", 0, "x10<super>9</super>/L", 150, 400, "150 - 400"),
    ]
    bioquimica = [
        fila_prueba("Glucosa", "glucosa", 0, "mg/dL", 70, 110, "70 - 110", "Suero · determinación casual"),
        fila_prueba("Hemoglobina glicada (HbA1c)", "hba1c", 1, "%", None, 5.6, "4,0 - 5,6"),
        fila_prueba("Urea", "urea", 0, "mg/dL", 15, 50, "15 - 50"),
        fila_prueba("Creatinina", "creatinina", 2, "mg/dL", *((0.5, 1.1, "0,50 - 1,10") if mujer else (0.7, 1.3, "0,70 - 1,30"))),
        fila_prueba("Filtrado glomerular estimado", "egfr", 0, "mL/min/1,73 m<super>2</super>", 60, None, "&gt; 60", "CKD-EPI 2021"),
        fila_prueba("Ácido úrico", "urico", 1, "mg/dL", *((2.4, 6.0, "2,4 - 6,0") if mujer else (3.4, 7.0, "3,4 - 7,0"))),
        fila_prueba("Sodio", "sodio", 0, "mmol/L", 135, 145, "135 - 145"),
        fila_prueba("Potasio", "potasio", 1, "mmol/L", 3.5, 5.1, "3,5 - 5,1"),
    ]
    hdl_min = 50 if mujer else 40
    lipidos = [
        fila_prueba("Colesterol total", "colesterol_total", 0, "mg/dL", None, 199, "&lt; 200"),
        fila_prueba("Colesterol HDL", "hdl", 0, "mg/dL", hdl_min, None, f"&gt; {hdl_min}"),
        fila_prueba("Colesterol LDL", "ldl", 0, "mg/dL", None, 129, "&lt; 130"),
        fila_prueba("Triglicéridos", "trigliceridos", 0, "mg/dL", None, 149, "&lt; 150"),
    ]
    hepatico = [
        fila_prueba("GOT (AST)", "got", 0, "U/L", None, 40, "&lt; 40"),
        fila_prueba("GPT (ALT)", "gpt", 0, "U/L", None, 41, "&lt; 41"),
        fila_prueba("Gamma-GT (GGT)", "ggt", 0, "U/L", None, 38 if mujer else 60, "&lt; 38" if mujer else "&lt; 60"),
        fila_prueba("Fosfatasa alcalina", "fosfatasa", 0, "U/L", 40, 130, "40 - 130"),
        fila_prueba("Bilirrubina total", "bilirrubina", 2, "mg/dL", None, 1.2, "0,10 - 1,20"),
    ]
    orina = [
        fila_prueba("Creatinina en orina", "creatinina_orina", 0, "mg/dL", 20, 300, "20 - 300"),
        fila_prueba("Albúmina en orina", "albumina_orina", 1, "mg/dL", None, 2.99, "&lt; 3,0"),
        fila_prueba("Cociente albúmina/creatinina", "acr", 1, "mg/g", None, 29.9, "&lt; 30"),
    ]
    return [("Hematología · Hemograma", hemograma), ("Bioquímica", bioquimica), ("Perfil lipídico", lipidos),
            ("Perfil hepático", hepatico), ("Bioquímica orina", orina)]


# ---------------------------------------------------------------- PDF

def pie_de_pagina(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINEA)
    canvas.line(15 * mm, 18 * mm, 195 * mm, 18 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SECUNDARIO)
    canvas.drawString(15 * mm, 13 * mm, AVISO_SINTETICO)
    canvas.drawRightString(195 * mm, 13 * mm, f"Página {doc.page}")
    canvas.restoreState()


def generar_pdf(paciente, examen, examen_n, total_examenes, carpeta, anteriores) -> Path:
    randid, periodo = paciente["patient_id"], examen["period"]
    fecha = examen["exam_time"].date()           # misma fecha que la base de datos y la app
    n_peticion = f"{randid}-{periodo}"
    if anteriores:
        tendencia = ('<font name="Symbol">↑</font> / <font name="Symbol">↓</font> indican aumento o descenso '
                     "respecto al último valor anterior de esa prueba en las analíticas del paciente. ")
    else:
        tendencia = "Es la primera analítica registrada del paciente, por lo que no se muestra tendencia. "
    ruta = carpeta / nombre_pdf(paciente, examen)

    doc = SimpleDocTemplate(str(ruta), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=24 * mm,
                            title=f"Analítica {n_peticion}", author=LABORATORIO, subject=AVISO_SINTETICO,
                            invariant=1)  # mismo contenido -> mismos bytes (sha256 estable)
    historia = [
        cabecera(n_peticion, fecha), Spacer(1, 5 * mm),
        datos_paciente(paciente, examen, examen_n, total_examenes), Spacer(1, 6 * mm),
        *[tabla_resultados(titulo, filas) for titulo, filas in secciones(paciente, examen, anteriores)],
        p("Los resultados en <b>negrita</b> están fuera de los valores de referencia del laboratorio. " + tendencia +
          "«No determinado» indica que la prueba no se realizó en este examen. "
          "Los valores de referencia son orientativos y deben interpretarse en el contexto clínico del paciente.", "nota"),
    ]
    doc.build(historia, onFirstPage=pie_de_pagina, onLaterPages=pie_de_pagina)
    return ruta


def nombre_pdf(paciente, examen) -> str:
    return f"analitica_{paciente['patient_id']}_periodo{examen['period']}_{examen['exam_time'].date().isoformat()}.pdf"


def generar(conn, randids: list[int] | None, salida: Path, limit: int | None = None,
            solo_nuevos: bool = False) -> list[Path]:
    """Genera los PDF; con solo_nuevos, salta los que ya existen (la generación es determinista)."""
    rutas = []
    for item in leer_pacientes(conn, randids, limit):
        paciente, examenes = item["patient"], item["exams"]
        carpeta = salida / str(paciente["patient_id"])
        carpeta.mkdir(parents=True, exist_ok=True)
        for n, examen in enumerate(examenes, start=1):
            if solo_nuevos and (carpeta / nombre_pdf(paciente, examen)).exists():
                continue
            rutas.append(generar_pdf(paciente, examen, n, len(examenes), carpeta, examenes[:n - 1]))
    return rutas


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera analíticas en PDF a partir de la base de datos")
    parser.add_argument("randid", nargs="*", type=int, help="RANDID de los pacientes")
    parser.add_argument("--all", action="store_true", help="Todo el cupo")
    parser.add_argument("--limit", type=int, help="Con --all: solo los N primeros pacientes")
    parser.add_argument("--out", type=Path, default=SALIDA, help=f"Carpeta de salida (por defecto {SALIDA})")
    parser.add_argument("--skip-existing", action="store_true", help="No regenera los PDF que ya existen")
    args = parser.parse_args()
    if not args.randid and not args.all:
        parser.error("Indica uno o varios RANDID o --all")
    inicio = time.perf_counter()
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        conn.execute("SET search_path = cardia, public")
        rutas = generar(conn, args.randid or None, args.out, args.limit, solo_nuevos=args.skip_existing)
    print(f"{len(rutas)} PDF generados en {args.out} ({time.perf_counter() - inicio:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
