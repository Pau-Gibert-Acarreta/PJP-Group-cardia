# Contrato de datos e indicadores

Esta es una preparación del frontend. No se ha implementado una base de datos, una API ni un cliente de machine learning.

## Entrada de mediciones

La tabla general, los indicadores y los hallazgos consultan la misma propiedad `patient.measurements`. Cada clave identifica una variable de origen y contiene su historial:

```json
{
  "id": "p001",
  "lastTest": "2026-11-10",
  "measurements": {
    "systolic": [
      { "value": 128, "date": "2026-08-07", "unit": "mmHg" },
      { "value": 148, "date": "2026-11-10", "unit": "mmHg" }
    ],
    "egfr": [
      { "value": 71, "date": "2026-08-07", "unit": "mL/min/1,73 m²" },
      { "value": 68, "date": "2026-11-10", "unit": "mL/min/1,73 m²" }
    ]
  }
}
```

`lastTest` es la fecha de la última prueba del paciente, mostrada en el resumen. Cada indicador tiene su propia fecha de medición: no se sustituye por `lastTest`. Los resultados históricos de laboratorio se consultan hasta la fecha del evento seleccionado.

El futuro adaptador debe entregar valores numéricos, fechas ISO válidas y unidades normalizadas. No se convierten unidades de forma implícita. `unit` es opcional cuando todos los valores ya vienen en la unidad declarada en la configuración. Si se incluye una unidad diferente a la configurada, esa medición se descarta. La clasificación KDIGO requiere eGFR en mL/min/1,73 m² y ACR en mg/g.

El historial se ordena por fecha. Para dos registros con el mismo instante se conserva el último recibido. No se interpretan `null`, cadenas numéricas, infinitos o fechas imposibles como mediciones válidas. Las fechas pueden ser días (`2026-11-10`) o instantes ISO con zona horaria.

Una variable ausente o un historial vacío se muestran como “Sin datos”. Con una sola medición el cambio es 0 y se indica “Sin valor anterior”. El valor 0 es una medición válida, no un dato ausente.

## Indicadores y nombres de origen

Edita `src/config/indicators.json`. La propiedad `indicators` define las filas y su orden:

```json
{
  "field": "systolic",
  "label": "PA sistólica",
  "shortLabel": "PA sistólica",
  "unit": "mmHg",
  "decimals": 0,
  "kind": "vital"
}
```

`field` debe coincidir exactamente con la clave entregada por el adaptador de la base de datos. Las claves actuales son provisionales; no presuponen un esquema real. Se han utilizado `systolic`, `diastolic`, `total_cholesterol`, `hdl_cholesterol`, `hba1c`, `acr`, `serum_creatinine` y `egfr`. La gráfica existente de LDL usa además `ldl`.

`kind` separa las exploraciones (`vital`) de las determinaciones de laboratorio (`lab`) en el detalle de las pruebas. `overviewFields` selecciona y ordena los indicadores numéricos en la tabla general. `kdigoFields` identifica las variables de eGFR y ACR.

Para renombrar una variable según la base de datos, actualiza su `field`, las referencias en `overviewFields` y `kdigoFields` si corresponde, y el `field` de sus reglas. Para añadir un indicador, añade su definición y entrega su historial; no hay que añadir una fila manualmente en el código de la vista. Para retirar una definición, retira también sus referencias o desactiva sus reglas. Si solo falta información de un paciente, basta con omitir su historial.

## Reglas de hallazgos

Edita `src/config/finding-rules.json`. Ejemplo:

```json
{
  "id": "systolic-rise",
  "enabled": true,
  "field": "systolic",
  "title": "Aumento de PA sistólica",
  "severity": "warning",
  "maxIntervalDays": 180,
  "conditions": [
    { "metric": "delta", "operator": "gte", "value": 15 }
  ]
}
```

Este ejemplo detecta una diferencia de al menos 15 mmHg entre las dos últimas mediciones válidas, si están separadas por un máximo de 180 días. Es un umbral ilustrativo para probar la interfaz, no una recomendación clínica.

Cada regla activa compara las dos últimas mediciones de su variable. Solo genera un hallazgo si ambas existen y se cumplen todas sus condiciones (AND). No busca un cambio antiguo que ya haya dejado de cumplirse. El hallazgo muestra su título, los dos valores, las dos fechas y el cambio.

| Propiedad | Significado |
| --- | --- |
| `id` | Identificador único de la regla. |
| `enabled` | `false` desactiva la regla. |
| `field` | Nombre técnico de la variable, igual que en indicadores y mediciones. |
| `title` | Texto breve que aparece en el hallazgo. |
| `severity` | `attention` o `warning`; cambia el estilo visual. |
| `maxIntervalDays` | Intervalo máximo entre ambas mediciones; opcional. |
| `conditions` | Una o más condiciones, todas necesarias. |

Las métricas disponibles son `current`, `previous`, `delta` (actual menos anterior) y `percent_change` ((actual menos anterior) / valor absoluto del anterior × 100). Los operadores disponibles son `gt`, `gte`, `lt`, `lte` y `eq`. Las diferencias usan la unidad del indicador; una diferencia de HbA1c de 0,5 es una diferencia de 0,5 puntos porcentuales. `percent_change` se expresa en porcentaje relativo y no se evalúa cuando el valor anterior es cero.

Añadir reglas con estos operadores solo requiere editar el JSON y recargar la página. No se introduce JavaScript, SQL ni expresiones ejecutables en el archivo. La configuración se valida al cargar; las referencias desconocidas y condiciones incorrectas producen un mensaje de error visible.

Las reglas se aplican por el orden del JSON. El estado vacío no implica que el paciente esté sano: indica que no hay mediciones comparables que cumplan las reglas configuradas.

## Minigráficas y cambios

Cada fila calcula su mínimo y máximo a partir del historial de ese indicador. La altura de la minigráfica utiliza exactamente ese intervalo y el eje horizontal representa el tiempo entre mediciones. Se muestran “mín” y “máx” sin dibujar ejes. Una serie constante o de un único valor aparece centrada. Los cambios numéricos se muestran con signo; no se interpreta automáticamente si una subida o bajada es favorable.

## Categoría KDIGO

La tabla muestra la combinación G/A de las últimas mediciones válidas de eGFR y ACR; no es un score numérico ni una probabilidad cardiovascular. Se utilizan los intervalos de la figura 13 de la [guía KDIGO 2024](https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf). Esto no evalúa la causa, la persistencia de tres meses ni los demás criterios necesarios para diagnosticar ERC. Si falta una medición comparable o las unidades no son las esperadas, se muestra “Sin datos”.

## Código de integración futura

- `src/data/demo/measurements.js`: genera los historiales ficticios actuales.
- `src/data/demo/patients.js`: construye los pacientes de demostración.
- `src/services/patient-service.js` y `src/services/notes-service.js`: única puerta de entrada a los datos para la interfaz. Aquí se sustituirán los datos de demostración por llamadas al backend (`src/services/api-client.js`).
- `src/domain/`: normaliza historiales (`measurements.js`), calcula cambios, evalúa las reglas (`findings.js`) y las categorías KDIGO (`kdigo.js`).
- `src/ui/components/`: presenta resumen, indicadores y hallazgos.

La integración futura deberá sustituir la entrega de datos de demostración por pacientes con el mismo contrato. La lógica clínica de presentación no necesita conocer cómo se consulta la base de datos. La normalización de nombres, tipos y unidades debe realizarse en ese adaptador, antes de evaluar las reglas. Consulta [arquitectura.md](arquitectura.md) para ver la estructura completa.
