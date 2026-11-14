// Sección "Indicadores clave" de la ficha: último valor, fecha, tendencia y cambio de cada indicador.
import { esc } from '../../utils/text.js';
import { getIndicatorRows } from '../../domain/measurements.js';
import { displayDate, formattedValue, formatDelta } from '../formatters.js';
import { icon } from '../icons.js';

// Minigráfica de un indicador con su mínimo y máximo.
export function indicatorTrend(summary) {
  if (!summary.series.length) return '<span class="missing-value">Sin historial</span>';
  const { series, min, max } = summary, first = series[0].time, last = series.at(-1).time;
  const coords = series.map(point => [
    first === last ? 74 : 5 + (point.time - first) / (last - first) * 138,
    min === max ? 20 : 35 - (point.value - min) / (max - min) * 30
  ]);
  const label = summary.label + '. ' + series.map(point => displayDate(point) + ': ' + formattedValue(point.value, summary) + ' ' + summary.unit).join('; ');
  return '<div class="indicator-trend"><svg viewBox="0 0 148 40" role="img" aria-label="' + esc(label) + '">' +
    (series.length > 1 ? '<polyline points="' + coords.map(point => point.join(',')).join(' ') + '" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>' : '') +
    coords.map(([x, y], index) =>
      '<circle cx="' + x + '" cy="' + y + '" r="' + (index === series.length - 1 ? '3.3' : '2.2') + '" fill="' + (index === series.length - 1 ? 'currentColor' : 'white') + '" stroke="currentColor" stroke-width="1.4">' +
      '<title>' + esc(displayDate(series[index]) + ' · ' + formattedValue(series[index].value, summary) + ' ' + summary.unit) + '</title></circle>').join('') +
    '</svg><div class="trend-range"><span>mín ' + formattedValue(min, summary) + '</span><span>máx ' + formattedValue(max, summary) + '</span></div></div>';
}

function indicatorRow(summary) {
  return '<tr data-indicator="' + esc(summary.field) + '">' +
    '<th scope="row">' + esc(summary.label) + '</th>' +
    '<td class="indicator-latest">' + (summary.latest ? '<strong>' + formattedValue(summary.latest.value, summary) + '</strong><span>' + esc(summary.unit) + '</span>' : '<span class="missing-value">Sin datos</span>') + '</td>' +
    '<td>' + (summary.latest ? '<time datetime="' + esc(summary.latest.date) + '">' + displayDate(summary.latest) + '</time>' : '<span class="missing-value">—</span>') + '</td>' +
    '<td>' + indicatorTrend(summary) + '</td>' +
    '<td><span class="indicator-change ' + (summary.delta === 0 ? 'unchanged' : '') + '">' + icon(summary.delta > 0 ? 'arrowUp' : summary.delta < 0 ? 'arrowDown' : 'activity') + formatDelta(summary) + ' <small>' + esc(summary.unit) + '</small></span>' +
    '<small class="comparison-date">' + (summary.previous ? 'Frente a ' + displayDate(summary.previous) : summary.latest ? 'Sin valor anterior' : 'Sin mediciones') + '</small></td>' +
    '</tr>';
}

export function renderIndicators(patient, config) {
  const rows = getIndicatorRows(patient, config);
  return '<section class="card key-indicators-card" aria-labelledby="key-indicators-title">' +
    '<div class="section-heading"><div><h2 id="key-indicators-title">' + icon('activity') + ' Indicadores clave <span class="count-pill">' + rows.length + '</span></h2>' +
    '<p>Últimos valores e historial de cada indicador, independientes de la predicción.</p></div>' +
    '<span class="subtle-label">Cada tendencia utiliza su propio mínimo y máximo</span></div>' +
    '<div class="indicator-table-scroll" role="region" aria-label="Indicadores con historial, desplazables horizontalmente" tabindex="0"><table class="indicator-table">' +
    '<thead><tr><th scope="col">Indicador</th><th scope="col">Último valor</th><th scope="col">Fecha del valor</th><th scope="col">Tendencia <span class="table-heading-hint">mín → máx</span></th><th scope="col">Cambio anterior</th></tr></thead><tbody>' +
    rows.map(indicatorRow).join('') +
    '</tbody></table></div><p class="indicator-footnote">El cambio se calcula frente a la medición anterior. Sin una medición comparable se muestra 0.</p></section>';
}
