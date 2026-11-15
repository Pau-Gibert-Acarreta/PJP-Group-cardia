// Ventanas de la ficha: detalle de un evento de la historia y gráfica ampliada.
import { state } from '../../app/state.js';
import { formatNumber as num, formatDate as date } from '../../utils/format.js';
import { esc } from '../../utils/text.js';
import { icon } from '../icons.js';
import { openModal } from '../components/modal.js';
import { chartData, chart } from '../components/chart.js';
import { api } from '../../services/api-client.js';

const EVENT_REPORTS = {
  ecg: 'Ritmo sinusal registrado a 72 lpm. Registro de ejemplo sin trazado adjunto.',
  medication: 'Se revisan la medicación habitual, la adherencia referida y los registros de presión arterial. Nota de tratamiento ficticia para explorar el historial.'
};
const DEFAULT_REPORT = 'Se documentan los antecedentes y se inicia el registro de indicadores para el seguimiento cardiovascular.';

// Origen de los datos de cada tipo de prueba (aviso al pie de la ventana).
const DATA_NOTES = {
  blood: 'Glucosa y lípidos del estudio de Framingham; HbA1c, creatinina y eGFR son sintéticos',
  urine: 'Cociente albúmina/creatinina sintético',
  vitals: 'Datos del estudio de Framingham'
};

// Contenido de la ventana de un evento. Cada prueba muestra solo sus propios resultados
// (los trae la API en e.results); el informe PDF solo existe para la analítica de sangre.
export function eventBody(e, patientName) {
  const results = Array.isArray(e.results) ? e.results : [];
  const detail = results.length
    ? '<table class="lab-table"><thead><tr><th>Determinación</th><th>Resultado</th><th>Unidad</th></tr></thead><tbody>' +
      results.map(r => '<tr><td>' + esc(r.label) + '</td><td><strong>' + num(r.value, r.decimals) + '</strong></td><td>' + esc(r.unit) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="event-report"><h3>Detalle del registro</h3><p>' + (Object.hasOwn(EVENT_REPORTS, e.id) ? EVENT_REPORTS[e.id] : DEFAULT_REPORT) + '</p></div>';
  const note = DATA_NOTES[e.testKind];
  return '<div class="event-dialog-meta"><span class="event-dialog-icon">' + icon(e.icon) + '</span><div><span class="eyebrow">' + esc(e.type) + '</span><p>' + date(e.date, true) + ' · ' + esc(patientName) + '</p></div></div>' +
    (e.description ? '<p class="event-description">' + esc(e.description) + '</p>' : '') + detail +
    (note ? '<div class="modal-note">' + icon('info') + ' ' + note + '</div>' : '') +
    '<div class="modal-footer">' + (e.documentId
      ? '<a class="button secondary" href="' + esc(api.documentUrl(e.documentId)) + '" target="_blank" rel="noopener">' + icon('note') + ' Ver informe del laboratorio (PDF)</a>'
      : '') +
    '<button class="button primary" data-action="close-modal">Cerrar detalle</button></div>';
}

export function openEvent(p, id) {
  const e = p.events.find(e => e.id === id);
  openModal(e.title, eventBody(e, p.name));
}

export function openExpandedChart(p) {
  const d = chartData(p, state);
  openModal('Evolución de ' + d.title,
    '<p class="dialog-subtitle">' + esc(p.name) + ' · ' + (state.period === 'all' ? 'todo el historial' : 'últimos ' + state.period + ' meses') + '</p>' +
    '<div class="expanded-chart">' + chart(p, state, true) + '</div>' +
    '<table class="lab-table"><thead><tr><th>Periodo</th><th>' + d.name + '</th></tr></thead><tbody>' +
    d.values.map((v, i) => '<tr><td>' + d.labels[i] + '</td><td>' + num(v, d.decimals) + ' ' + d.unit + '</td></tr>').join('') + '</tbody></table>', true);
}
