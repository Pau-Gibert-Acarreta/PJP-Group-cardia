# Arquitectura del frontend

Cardia es una aplicación web sin dependencias ni paso de compilación: HTML, CSS y JavaScript con módulos ES nativos. El navegador carga `index.html`, que enlaza `src/styles/main.css` y `src/main.js`.

## Estructura

```
index.html                 Página única: #app, #modal y #toast
src/
├── main.js                Punto de entrada: registra eventos y arranca
├── app/                   Orquestación (sin HTML)
│   ├── state.js           Estado de la interfaz y configuración clínica cargada
│   ├── router.js          Rutas por hash: "#" listado, "#paciente/<id>" ficha
│   ├── render.js          Pinta la estructura y la vista de la ruta actual
│   ├── actions.js         Qué hace cada data-action (filtros, notas, seguimiento…)
│   ├── events.js          Listeners del navegador (clic, input, change, submit, hashchange)
│   └── bootstrap.js       Carga la configuración y pinta la app
├── services/              Acceso a datos: la única capa que sabe de dónde vienen
│   ├── patient-service.js Pacientes y seguimiento
│   ├── notes-service.js   Notas de consulta
│   ├── risk-service.js    Ajuste clínico de la clasificación de riesgo
│   ├── config-service.js  Carga y validación de src/config/*.json
│   ├── export-service.js  Exportación CSV del listado
│   ├── storage.js         localStorage tolerante a fallos
│   └── api-client.js      Cliente HTTP del backend (preparado, aún sin usar)
├── domain/                Lógica clínica pura: sin DOM, testeable con Node
│   ├── risk.js            Niveles del semáforo y clasificación final (modelo o ajuste clínico)
│   ├── patient-filters.js Búsqueda, filtros y orden del listado
│   ├── measurements.js    Series de mediciones y resumen (último, anterior, cambio)
│   ├── findings.js        Reglas de hallazgos
│   ├── kdigo.js           Categorías G/A de KDIGO
│   ├── indicator-status.js Colores por rango y dirección del cambio
│   └── clinical-config.js Validación de la configuración
├── data/demo/             Pacientes y mediciones ficticios (se sustituirán por el backend)
├── config/                Indicadores, rangos de color y reglas (editables sin tocar código)
├── ui/                    Todo lo que genera HTML
│   ├── views/             Pantallas completas: layout, listado, ficha, estados
│   ├── components/        Piezas reutilizables: tabla, gráfica, hallazgos, modal, toast…
│   ├── dialogs/           Contenido de las ventanas modales
│   ├── icons.js           Iconos SVG
│   ├── formatters.js      Formato de valores clínicos
│   └── dom.js             Atajo $() para el DOM
├── utils/                 Formato de números y fechas, escape de HTML
└── styles/                CSS dividido por zonas; main.css los importa en orden
```

## Reglas de dependencia

Las importaciones van en un solo sentido, de arriba abajo:

```
main → app → ui/views → ui/components → domain → utils
            ↘ services → data/demo, domain
```

- `domain/` y `utils/` no importan nada de la interfaz ni de los servicios. Por eso las pruebas de `tests/` se ejecutan en Node sin navegador.
- Las vistas (`ui/`) piden los datos a `services/`, nunca a `data/demo/` directamente, y leen el estado de `app/state.js`.
- Solo `app/actions.js` cambia el estado (`app/state.js`) en respuesta a lo que hace el usuario.

## Flujo de una interacción

1. El HTML generado lleva `data-action="..."` en cada botón (por ejemplo `data-action="followup"`).
2. `app/events.js` recibe el clic con un único listener sobre `#app`.
3. `app/actions.js` ejecuta la acción: actualiza `state`, llama al servicio si hay que guardar algo y vuelve a pintar la parte afectada.

Para añadir un botón nuevo: pon `data-action="mi-accion"` en el HTML y añade un `case 'mi-accion'` en `handleAction`.

## Conectar el backend

Hoy los datos salen de `data/demo/` y los cambios se guardan en `localStorage`. Para integrarlo con el backend:

1. Ajusta los endpoints de `services/api-client.js` al contrato real (`API_BASE_URL` y rutas).
2. Cambia el interior de `services/patient-service.js` y `services/notes-service.js` para que llamen a `api`. Las vistas no cambian mientras las funciones devuelvan pacientes con el formato de [data-contract.md](data-contract.md) (`patient.measurements[field] = [{ value, date, unit }]`).
3. Las llamadas al backend son asíncronas. Cuando se conecten, `bootstrap.js` deberá esperar a que lleguen los pacientes (`await`) antes de pintar, igual que ya hace con la configuración clínica.
4. Los resultados de los modelos de riesgo (SCORE2, SCORE2-OP, KFRE, modelo propio) llegarán por `api.getRiskAssessments` y sustituirán a `p.risk` y `p.factors`, que hoy son simulados.

## Ajuste clínico de la clasificación de riesgo

El modelo calcula una probabilidad (`p.risk`) y de ella sale su clasificación (alto ≥ 20 %, medio 10–20 %, bajo < 10 %). El médico puede cambiar la clasificación desde la ficha (botón «Ajustar» en Riesgo cardiovascular), pero nunca la probabilidad.

- El ajuste se guarda en `p.riskOverride = { level, reason, author, date, modelLevel }` mediante `services/risk-service.js`.
- `domain/risk.js → effectiveRiskLevel(p)` devuelve la clasificación final. Es la que usan el listado, los filtros, los contadores, «Prioridad clínica» y la exportación CSV.
- El motivo es obligatorio cuando la clasificación no coincide con la del modelo. Elegir la del modelo elimina el ajuste.
- En el backend, `api.setRiskClassification` y `api.clearRiskClassification` deberían guardar también el historial de ajustes para auditoría.

## Estilos

`src/styles/main.css` importa los archivos numerados en el mismo orden que la hoja original, así que la cascada no ha cambiado. Para modificar algo, busca la zona (por ejemplo `06-patient-detail.css` para la ficha). Los ajustes visuales más recientes (textos en negro, tonos clínicos) están en `10-refinements.css` y prevalecen sobre los anteriores. Añade archivos nuevos al final de `main.css`.

## Comprobaciones

```sh
node scripts/check.mjs
```

Revisa la sintaxis de todos los módulos de `src/` (incluidas las subcarpetas) y ejecuta las pruebas de `tests/`.
