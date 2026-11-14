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
│   ├── patient-service.js Pacientes (cupo y ficha) y seguimiento, desde la API
│   ├── patient-adapter.js Paciente de la API → objeto de las vistas (+ riesgo simulado)
│   ├── notes-service.js   Notas de consulta, desde la API
│   ├── risk-service.js    Ajuste clínico de la clasificación de riesgo
│   ├── config-service.js  Carga y validación de src/config/*.json
│   ├── export-service.js  Exportación CSV del listado
│   ├── storage.js         localStorage tolerante a fallos
│   └── api-client.js      Cliente HTTP del Core Backend API
├── domain/                Lógica clínica pura: sin DOM, testeable con Node
│   ├── risk.js            Niveles del semáforo y clasificación final (modelo o ajuste clínico)
│   ├── patient-filters.js Búsqueda, filtros y orden del listado
│   ├── measurements.js    Series de mediciones y resumen (último, anterior, cambio)
│   ├── findings.js        Reglas de hallazgos
│   ├── kdigo.js           Categorías G/A de KDIGO
│   ├── indicator-status.js Colores por rango y dirección del cambio
│   └── clinical-config.js Validación de la configuración
├── data/demo/             Riesgo simulado y pacientes de ejemplo para las pruebas
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

El frontend está conectado al Core Backend API (`backend/`). `scripts/serve.mjs` reenvía `/api/*` al backend, así que `services/api-client.js` usa rutas relativas.

| Dato | De dónde sale |
| --- | --- |
| Identidad, contacto, edad, sexo, antecedentes | `GET /api/v1/patients` (listado) y `GET /api/v1/patients/{id}` (contacto) |
| Mediciones | Listado completo con `include_measurements=true` |
| Línea temporal y notas | Ficha (`GET /patients/{id}`), pedida al abrir el paciente |
| Seguimiento | `PUT /patients/{id}/followup` |
| Notas nuevas o editadas | `POST /patients/{id}/notes`, `PUT /patients/{id}/notes/{noteId}` |
| Riesgo, factores e historial de riesgo | Simulados: `data/demo/simulated-risk.js` |
| Ajuste de la clasificación de riesgo | `localStorage` (`services/risk-service.js`) |
| Hallazgos | Calculados en el navegador (`domain/findings.js`) con `finding-rules.json` |

Flujo:

1. `bootstrap.js` carga la configuración y el cupo completo (`patient-service.loadPatients`). El listado filtra, ordena y cuenta en el navegador, como antes.
2. `services/patient-adapter.js` convierte cada paciente de la API al objeto que usan las vistas y le añade el riesgo simulado.
3. Al abrir una ficha, `render.js` pide los datos que faltan (`loadPatientDetail`) y pinta cuando llegan.
4. Si falla el servidor, se muestra un error con «Reintentar»; si falla una nota o el seguimiento, un aviso, y no se pierde lo escrito.

Cuando exista el Motor de Riesgo (4B), `api.getRiskAssessments` sustituirá a `simulateRisk` en el adaptador, y el ajuste de clasificación pasará a `api.setRiskClassification`, que el backend ya guarda con autor, fecha y motivo.

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
