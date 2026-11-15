// Tarjeta "Casos similares": el paciente estudiado frente a sus 7 vecinos más parecidos (KNN).
// Filas = variables, columnas = paciente + casos, para comparar de un vistazo.
import { formatNumber as num, formatDate as date } from '../../utils/format.js';
import { esc } from '../../utils/text.js';
import { icon } from '../icons.js';

const GROUPS = [['context', 'Contexto'], ['value', 'Valores en la prueba comparada'], ['trend', 'Tendencia (cambio por año)']];

// Diferencia respecto al paciente, en desviaciones estándar.
const closeness = diff => diff === null || diff === undefined ? 'missing' : diff <= 0.5 ? 'close' : diff <= 1 ? 'near' : 'far';

function formatValue(feature, value) {
  if (value === null || value === undefined) return '<span class="missing-value">—</span>';
  if (feature.kind === 'bool') return value >= 0.5 ? 'Sí' : 'No';
  if (feature.kind === 'sex') return value >= 0.5 ? 'Hombre' : 'Mujer';
  const text = num(value, feature.decimals);
  return feature.group === 'trend' && value > 0 ? '+' + text : text;
}

const weightDots = weight => {
  const n = weight >= 2 ? 3 : weight >= 1 ? 2 : 1;
  return '<span class="knn-weight" title="Peso ' + num(weight, 2) + ' en la búsqueda" aria-label="Peso ' + num(weight, 2) + '">' +
    '●'.repeat(n) + '<span class="knn-weight-off">' + '●'.repeat(3 - n) + '</span></span>';
};

function outcomeCell(o, key) {
  if (!o) return '<td><span class="missing-value">—</span></td>';
  const item = o[key];
  if (item.status === 'event') return '<td class="knn-outcome event">Sí <small>a los ' + num(item.years, 1) + ' años</small></td>';
  if (item.status === 'before') return '<td class="knn-outcome before">Previo <small>al examen</small></td>';
  return '<td class="knn-outcome none">No <small>' + num(item.years, 1) + ' años</small></td>';
}

function summaryText(data) {
  const { cvdEvents, deaths, withOutcome } = data.summary;
  const years = data.neighbors.filter(n => n.outcome?.cvd.status === 'event').map(n => n.outcome.cvd.years);
  const range = years.length ? ' (entre ' + num(Math.min(...years), 1) + ' y ' + num(Math.max(...years), 1) + ' años después)' : '';
  return '<strong>' + cvdEvents + ' de ' + withOutcome + '</strong> casos parecidos tuvieron un evento cardiovascular' + range +
    ' y <strong>' + deaths + '</strong> fallecieron durante el seguimiento.';
}

function table(data) {
  const head = '<thead><tr><th scope="col" class="knn-var">Variable</th><th scope="col" class="knn-self">Este paciente</th>' +
    data.neighbors.map(n => '<th scope="col">' + esc(n.label) + '<small>Similitud ' + num(n.similarity, 0) + ' %</small></th>').join('') + '</tr></thead>';

  const outcomeRows = [['cvd', 'Evento cardiovascular'], ['death', 'Fallecimiento']].map(([key, label]) =>
    '<tr class="knn-outcome-row"><th scope="row">' + label + '</th><td class="knn-self"><span class="missing-value">Desconocido</span></td>' +
    data.neighbors.map(n => outcomeCell(n.outcome, key)).join('') + '</tr>').join('') +
    '<tr class="knn-outcome-row"><th scope="row">Prueba comparada</th><td class="knn-self">' + date(data.referenceTime) + '</td>' +
    data.neighbors.map(n => '<td>Examen ' + (n.exam.period ?? '—') + '</td>').join('') + '</tr>';

  const groupRows = GROUPS.map(([group, title]) => {
    const features = data.features.filter(f => f.group === group);
    return '<tr class="knn-group"><th colspan="' + (data.neighbors.length + 2) + '">' + title + '</th></tr>' +
      features.map(f =>
        '<tr><th scope="row"><span>' + esc(f.label) + (f.unit ? ' <small>' + esc(f.unit) + '</small>' : '') + '</span>' + weightDots(f.weight) + '</th>' +
        '<td class="knn-self">' + formatValue(f, data.patient.values[f.key]) + '</td>' +
        data.neighbors.map(n => '<td class="knn-' + closeness(n.differences[f.key]) + '">' + formatValue(f, n.values[f.key]) + '</td>').join('') +
        '</tr>').join('');
  }).join('');

  return '<div class="table-scroll knn-scroll" role="region" aria-label="Comparación con casos similares, desplazable horizontalmente" tabindex="0">' +
    '<table class="knn-table">' + head + '<tbody>' + outcomeRows + groupRows + '</tbody></table></div>';
}

const legend = () =>
  '<div class="knn-legend"><span><i class="knn-swatch close"></i> Parecido (≤ 0,5 DE)</span><span><i class="knn-swatch near"></i> Algo distinto (≤ 1 DE)</span>' +
  '<span><i class="knn-swatch far"></i> Distinto (&gt; 1 DE)</span><span>' + weightDots(2) + ' Peso de la variable en la búsqueda</span></div>';

function body(state) {
  if (state.loading) return '<div class="knn-status" aria-busy="true">Buscando casos parecidos…</div>';
  if (state.error) return '<div class="knn-status">' + icon('info') + ' ' + esc(state.error) + '</div>';
  const data = state.data;
  const reference = 'Se compara el estado del paciente en su última prueba (' + date(data.referenceTime) + ').';
  return '<p class="knn-reference">' + reference + '</p>' +
    '<p class="knn-summary">' + summaryText(data) + '</p>' + table(data) + legend();
}

export function similarCasesCard(state) {
  return '<section class="card knn-card" id="similar-cases"><div class="section-heading"><div><h2>' + icon('users') + ' Casos similares</h2>' +
    '<p>Los 7 pacientes del histórico cuyo estado y evolución más se parecían, y qué les pasó después.</p></div></div>' +
    '<div id="similar-cases-body">' + body(state) + '</div></section>';
}

export const similarCasesBody = state => body(state);
