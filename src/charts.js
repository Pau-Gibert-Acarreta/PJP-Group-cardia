import { formatNumber as num } from './data.js';
import { icon } from './ui.js';
export function chartTabs(state) {
  return [['ldl', 'Colesterol LDL'], ['pressure', 'Presión arterial'], ['hba1c', 'HbA1c']].map(([key, label]) => '<button class="' + (state.chart === key ? 'selected' : '') + '" data-action="chart" data-chart="' + key + '" aria-pressed="' + (state.chart === key) + '">' + label + '</button>').join('');
}
export function chartData(p, state) {
  const labels = ['Dic 25', 'Feb 26', 'Abr 26', 'Jun 26', 'Ago 26', 'Nov 26'];
  const values = p.history[state.chart], start = state.period === '6' ? 3 : 0;
  return { values: values.slice(start), labels: labels.slice(start), unit: state.chart === 'ldl' ? 'mg/dL' : state.chart === 'pressure' ? 'mmHg' : '%', name: state.chart === 'ldl' ? 'Colesterol LDL' : state.chart === 'pressure' ? 'Presión arterial sistólica' : 'HbA1c' };
}
export function chart(p, state, expanded = false) {
  const { values, labels, unit, name } = chartData(p, state);
  const step = state.chart === 'hba1c' ? .5 : 10;
  const low = Math.floor(Math.min(...values) / step) * step - step;
  const high = Math.ceil(Math.max(...values) / step) * step + step;
  const coords = values.map((v, i) => [52 + i * (490 / (values.length - 1)), 190 - (v - low) / (high - low) * 150]);
  const points = coords.map(x => x.join(',')).join(' '), diff = values.at(-1) - values[0], fill = 'chart-fill' + (expanded ? '-expanded' : '');
  return '<div class="chart-summary"><strong>' + num(values.at(-1), state.chart === 'hba1c' ? 1 : 0) + '<span>' + unit + '</span></strong><span class="chart-change">' + icon(diff <= 0 ? 'arrowDown' : 'arrowUp') + num(Math.abs(diff), state.chart === 'hba1c' ? 1 : 0) + ' ' + unit + ' <small>en el periodo</small></span></div><svg class="main-chart" viewBox="0 0 580 235" role="img" aria-label="' + name + ': ' + values.map((v, i) => labels[i] + ', ' + num(v, 1) + ' ' + unit).join('; ') + '"><defs><linearGradient id="' + fill + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#128a80" stop-opacity=".14"/><stop offset="100%" stop-color="#128a80" stop-opacity=".005"/></linearGradient></defs>' +
    Array.from({ length: 5 }, (_, i) => { const y = 40 + i * 37.5, v = high - i * (high - low) / 4; return '<line x1="52" y1="' + y + '" x2="548" y2="' + y + '" class="chart-grid-line"/><text x="36" y="' + (y + 4) + '" text-anchor="end">' + num(v, state.chart === 'hba1c' ? 1 : 0) + '</text>'; }).join('') +
    '<polygon points="52,190 ' + points + ' 542,190" fill="url(#' + fill + ')"/><polyline points="' + points + '" fill="none" stroke="#0c8279" stroke-width="2.8" stroke-linejoin="round"/>' +
    coords.map(([x, y], i) => '<circle cx="' + x + '" cy="' + y + '" r="4.5" fill="white" stroke="#0c8279" stroke-width="2.5"><title>' + labels[i] + ': ' + num(values[i], 1) + ' ' + unit + '</title></circle><text x="' + x + '" y="222" text-anchor="middle">' + labels[i] + '</text>').join('') + '</svg><div class="chart-legend"><span class="line-swatch"></span> ' + name + '<span class="chart-source">Datos de demostración</span></div>';
}
export function metrics(p, previous = false) {
  const m = p.metrics;
  return [
    { name: 'Colesterol LDL', value: previous ? p.history.ldl[1] : m.ldl, unit: 'mg/dL', caption: 'Perfil lipídico' },
    { name: 'Presión arterial', value: (previous ? p.history.pressure[1] : m.systolic) + '/' + m.diastolic, unit: 'mmHg', caption: 'Última exploración' },
    { name: 'Hemoglobina glicosilada', value: num(previous ? p.history.hba1c[1] : m.hba1c, 1), unit: '%', caption: 'HbA1c' },
    { name: 'Filtrado glomerular', value: previous ? m.egfr + 4 : m.egfr, unit: 'mL/min/1,73 m²', caption: 'FGe estimado' },
    { name: 'Albuminuria', value: previous ? m.acr + 6 : m.acr, unit: 'mg/g', caption: 'Cociente albúmina/creatinina' },
    { name: 'Índice de masa corporal', value: num(m.bmi, 1), unit: 'kg/m²', caption: 'Última exploración' }
  ];
}

