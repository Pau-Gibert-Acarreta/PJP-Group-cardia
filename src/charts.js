import { formatNumber as num } from './data.js';
import { icon } from './ui.js';
import { getSeries } from './clinical.js';
export function chartTabs(state) {
  return [['ldl', 'Colesterol LDL'], ['pressure', 'Presión arterial'], ['hba1c', 'HbA1c']].map(([key, label]) => '<button class="' + (state.chart === key ? 'selected' : '') + '" data-action="chart" data-chart="' + key + '" aria-pressed="' + (state.chart === key) + '">' + label + '</button>').join('');
}
export function chartData(p, state) {
  const definitions = {
    ldl: { field: 'ldl', unit: 'mg/dL', name: 'Colesterol LDL' },
    pressure: { field: 'systolic', unit: 'mmHg', name: 'Presión arterial sistólica' },
    hba1c: { field: 'hba1c', unit: '%', name: 'HbA1c' }
  };
  const definition = definitions[state.chart] || definitions.ldl;
  let series = getSeries(p, definition);
  if (series.length) {
    const cutoff = new Date(series.at(-1).time);
    cutoff.setUTCMonth(cutoff.getUTCMonth() - Number(state.period));
    series = series.filter(point => point.time >= cutoff.getTime());
  }
  const label = new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit', timeZone: 'UTC' });
  return { values: series.map(point => point.value), times: series.map(point => point.time), labels: series.map(point => label.format(new Date(point.time))), unit: definition.unit, name: definition.name };
}
export function chart(p, state, expanded = false) {
  const { values, times, labels, unit, name } = chartData(p, state);
  if (!values.length) return '<div class="empty-state"><h3>Sin mediciones disponibles</h3><p>No hay datos de este indicador en el periodo seleccionado.</p></div>';
  const step = state.chart === 'hba1c' ? .5 : 10;
  const low = Math.floor(Math.min(...values) / step) * step - step;
  const high = Math.ceil(Math.max(...values) / step) * step + step;
  const coords = values.map((v, i) => [times.at(-1) === times[0] ? 297 : 52 + (times[i] - times[0]) / (times.at(-1) - times[0]) * 490, 190 - (v - low) / (high - low) * 150]);
  const points = coords.map(x => x.join(',')).join(' '), diff = values.at(-1) - values[0], fill = 'chart-fill' + (expanded ? '-expanded' : '');
  return '<div class="chart-summary"><strong>' + num(values.at(-1), state.chart === 'hba1c' ? 1 : 0) + '<span>' + unit + '</span></strong><span class="chart-change">' + icon(diff <= 0 ? 'arrowDown' : 'arrowUp') + num(Math.abs(diff), state.chart === 'hba1c' ? 1 : 0) + ' ' + unit + ' <small>en el periodo</small></span></div><svg class="main-chart" viewBox="0 0 580 235" role="img" aria-label="' + name + ': ' + values.map((v, i) => labels[i] + ', ' + num(v, 1) + ' ' + unit).join('; ') + '"><defs><linearGradient id="' + fill + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#128a80" stop-opacity=".14"/><stop offset="100%" stop-color="#128a80" stop-opacity=".005"/></linearGradient></defs>' +
    Array.from({ length: 5 }, (_, i) => { const y = 40 + i * 37.5, v = high - i * (high - low) / 4; return '<line x1="52" y1="' + y + '" x2="548" y2="' + y + '" class="chart-grid-line"/><text x="36" y="' + (y + 4) + '" text-anchor="end">' + num(v, state.chart === 'hba1c' ? 1 : 0) + '</text>'; }).join('') +
    '<polygon points="52,190 ' + points + ' 542,190" fill="url(#' + fill + ')"/><polyline points="' + points + '" fill="none" stroke="#0c8279" stroke-width="2.8" stroke-linejoin="round"/>' +
    coords.map(([x, y], i) => '<circle cx="' + x + '" cy="' + y + '" r="4.5" fill="white" stroke="#0c8279" stroke-width="2.5"><title>' + labels[i] + ': ' + num(values[i], 1) + ' ' + unit + '</title></circle><text x="' + x + '" y="222" text-anchor="middle">' + labels[i] + '</text>').join('') + '</svg><div class="chart-legend"><span class="line-swatch"></span> ' + name + '<span class="chart-source">Datos de demostración</span></div>';
}
