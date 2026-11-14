// Ventanas de la ficha: detalle de un evento de la historia y gráfica ampliada.
import { state, clinical } from '../../app/state.js';
import { getSeries } from '../../domain/measurements.js';
import { formatNumber as num, formatDate as date } from '../../utils/format.js';
import { esc } from '../../utils/text.js';
import { icon } from '../icons.js';
import { openModal } from '../components/modal.js';
import { chartData, chart } from '../components/chart.js';

const EVENT_REPORTS = {
  ecg: 'Ritmo sinusal registrado a 72 lpm. Registro de ejemplo sin trazado adjunto.',
  medication: 'Se revisan la medicación habitual, la adherencia referida y los registros de presión arterial. Nota de tratamiento ficticia para explorar el historial.'
};
const DEFAULT_REPORT = 'Se documentan los antecedentes y se inicia el registro de indicadores para el seguimiento cardiovascular.';

export function openEvent(p, id) {
  const e = p.events.find(e => e.id === id);
  const lab = e.type === 'Laboratorio';
  // Resultados de laboratorio vigentes en la fecha del evento.
  const results = clinical.config.indicators.filter(item => item.kind !== 'vital')
    .map(item => ({ ...item, latest: getSeries(p, item).filter(point => point.date.slice(0, 10) <= e.date).at(-1) }))
    .filter(item => item.latest);
  const detail = lab
    ? '<table class="lab-table"><thead><tr><th>Determinación</th><th>Resultado</th><th>Unidad</th></tr></thead><tbody>' +
      results.map(item => '<tr><td>' + esc(item.label) + '</td><td><strong>' + num(item.latest.value, item.decimals) + '</strong></td><td>' + esc(item.unit) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="event-report"><h3>Detalle del registro</h3><p>' + (Object.hasOwn(EVENT_REPORTS, id) ? EVENT_REPORTS[id] : DEFAULT_REPORT) + '</p></div>';
  openModal(e.title,
    '<div class="event-dialog-meta"><span class="event-dialog-icon">' + icon(e.icon) + '</span><div><span class="eyebrow">' + e.type + '</span><p>' + date(e.date, true) + ' · ' + p.name + '</p></div></div>' +
    '<p class="event-description">' + e.description + '</p>' + detail +
    '<div class="modal-note">' + icon('info') + ' Documento de ejemplo · resultados ficticios</div><div class="modal-footer"><button class="button primary" data-action="close-modal">Cerrar detalle</button></div>');
}

export function openExpandedChart(p) {
  const d = chartData(p, state);
  openModal('Evolución de ' + d.title,
    '<p class="dialog-subtitle">' + p.name + ' · últimos ' + state.period + ' meses</p>' +
    '<div class="expanded-chart">' + chart(p, state, true) + '</div>' +
    '<table class="lab-table"><thead><tr><th>Periodo</th><th>' + d.name + '</th></tr></thead><tbody>' +
    d.values.map((v, i) => '<tr><td>' + d.labels[i] + '</td><td>' + num(v, d.decimals) + ' ' + d.unit + '</td></tr>').join('') + '</tbody></table>', true);
}
