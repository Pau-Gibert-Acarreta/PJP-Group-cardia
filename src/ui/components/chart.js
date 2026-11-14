// Gráfica "Evolución de indicadores" con pestañas por indicador y tooltip en cada punto.
import { formatNumber as num } from '../../utils/format.js';
import { getSeries } from '../../domain/measurements.js';
import { icon } from '../icons.js';

// Indicadores disponibles en la gráfica, en el orden de las pestañas.
// field: clave en patient.measurements · step: separación de las líneas del eje vertical.
export const CHART_OPTIONS = [
  { key: 'ldl', group: 'Lípidos', field: 'ldl', label: 'Colesterol LDL', name: 'Colesterol LDL', title: 'colesterol LDL', unit: 'mg/dL', decimals: 0, step: 10 },
  { key: 'systolic', group: 'Presión arterial', field: 'systolic', label: 'PA sistólica', name: 'Presión arterial sistólica', title: 'presión arterial sistólica', unit: 'mmHg', decimals: 0, step: 10 },
  { key: 'diastolic', group: 'Presión arterial', field: 'diastolic', label: 'PA diastólica', name: 'Presión arterial diastólica', title: 'presión arterial diastólica', unit: 'mmHg', decimals: 0, step: 5 },
  { key: 'total_cholesterol', group: 'Lípidos', field: 'total_cholesterol', label: 'Colesterol total', name: 'Colesterol total', title: 'colesterol total', unit: 'mg/dL', decimals: 0, step: 10 },
  { key: 'hdl_cholesterol', group: 'Lípidos', field: 'hdl_cholesterol', label: 'Colesterol HDL', name: 'Colesterol HDL', title: 'colesterol HDL', unit: 'mg/dL', decimals: 0, step: 5 },
  { key: 'hba1c', group: 'Metabolismo', field: 'hba1c', label: 'HbA1c', name: 'HbA1c', title: 'HbA1c', unit: '%', decimals: 1, step: .5 },
  { key: 'acr', group: 'Función renal', field: 'acr', label: 'Albuminuria (ACR)', name: 'Albuminuria (ACR)', title: 'albuminuria (ACR)', unit: 'mg/g', decimals: 0, step: 10 },
  { key: 'serum_creatinine', group: 'Función renal', field: 'serum_creatinine', label: 'Creatinina sérica', name: 'Creatinina sérica', title: 'creatinina sérica', unit: 'mg/dL', decimals: 2, step: .1 },
  { key: 'egfr', group: 'Función renal', field: 'egfr', label: 'eGFR', name: 'eGFR', title: 'eGFR', unit: 'mL/min/1,73 m²', decimals: 0, step: 5 }
];

// Claves antiguas que se siguen aceptando.
const ALIASES = { pressure: 'systolic' };

export const chartOption = key => CHART_OPTIONS.find(option => option.key === (ALIASES[key] || key)) || CHART_OPTIONS[0];

const GROUP_ORDER = ['Presión arterial', 'Lípidos', 'Metabolismo', 'Función renal'];

// Selector desplegable de indicador: muestra el elegido y, al abrirlo, todos agrupados con su último valor.
export function chartPicker(p, state) {
  const selected = chartOption(state.chart);
  const option = o => {
    const latest = getSeries(p, o).at(-1);
    const isSelected = o.key === selected.key;
    return '<button type="button" class="chart-option' + (isSelected ? ' selected' : '') + '" data-action="chart" data-chart="' + o.key + '" aria-pressed="' + isSelected + '">' +
      '<span class="chart-option-check">' + (isSelected ? icon('check') : '') + '</span>' +
      '<span class="chart-option-name">' + o.label + '</span>' +
      '<span class="chart-option-value">' + (latest ? num(latest.value, o.decimals) + ' <small>' + o.unit + '</small>' : '<small>Sin datos</small>') + '</span></button>';
  };
  return '<details class="chart-picker"><summary class="chart-picker-trigger" aria-label="Elegir indicador de la gráfica">' +
    '<span class="chart-picker-text"><small>Indicador</small><strong>' + selected.label + '</strong></span>' + icon('down') + '</summary>' +
    '<div class="chart-picker-menu">' +
    GROUP_ORDER.map(group => '<div class="chart-option-group"><span class="chart-option-group-label">' + group + '</span>' +
      CHART_OPTIONS.filter(o => o.group === group).map(option).join('') + '</div>').join('') +
    '</div></details>';
}

// Valores, fechas y etiquetas del indicador seleccionado dentro del periodo (6 o 12 meses).
export function chartData(p, state) {
  const definition = chartOption(state.chart);
  let series = getSeries(p, definition);
  if (series.length) {
    const cutoff = new Date(series.at(-1).time);
    cutoff.setUTCMonth(cutoff.getUTCMonth() - Number(state.period));
    series = series.filter(point => point.time >= cutoff.getTime());
  }
  const label = new Intl.DateTimeFormat('es-ES', { month: 'short', year: '2-digit', timeZone: 'UTC' });
  return { values: series.map(point => point.value), times: series.map(point => point.time), labels: series.map(point => label.format(new Date(point.time))), unit: definition.unit, name: definition.name, title: definition.title, decimals: definition.decimals, step: definition.step };
}

const fullDate = new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });

export function chart(p, state, expanded = false) {
  const { values, times, labels, unit, name, decimals, step } = chartData(p, state);
  if (!values.length) return '<div class="empty-state"><h3>Sin mediciones disponibles</h3><p>No hay datos de este indicador en el periodo seleccionado.</p></div>';
  const low = Math.floor(Math.min(...values) / step) * step - step;
  const high = Math.ceil(Math.max(...values) / step) * step + step;
  const coords = values.map((v, i) => [times.at(-1) === times[0] ? 297 : 52 + (times[i] - times[0]) / (times.at(-1) - times[0]) * 490, 190 - (v - low) / (high - low) * 150]);
  const points = coords.map(x => x.join(',')).join(' '), diff = values.at(-1) - values[0], fill = 'chart-fill' + (expanded ? '-expanded' : '');

  // Último valor y, debajo, la tendencia del periodo.
  const summary = '<div class="chart-summary"><strong>' + num(values.at(-1), decimals) + '<span>' + unit + '</span></strong>' +
    '<span class="chart-change">' + icon(diff <= 0 ? 'arrowDown' : 'arrowUp') + num(Math.abs(diff), decimals) + ' ' + unit + ' <small>en el periodo</small></span></div>';

  const svgOpen = '<svg class="main-chart" viewBox="0 0 580 235" role="img" aria-label="' + name + ': ' + values.map((v, i) => labels[i] + ', ' + num(v, 1) + ' ' + unit).join('; ') + '">' +
    '<defs><linearGradient id="' + fill + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#128a80" stop-opacity=".14"/><stop offset="100%" stop-color="#128a80" stop-opacity=".005"/></linearGradient></defs>';

  // Líneas de referencia y valores del eje vertical.
  const grid = Array.from({ length: 5 }, (_, i) => {
    const y = 40 + i * 37.5, v = high - i * (high - low) / 4;
    return '<line x1="52" y1="' + y + '" x2="548" y2="' + y + '" class="chart-grid-line"/><text x="36" y="' + (y + 4) + '" text-anchor="end">' + num(v, decimals) + '</text>';
  }).join('');

  const line = '<polygon points="52,190 ' + points + ' 542,190" fill="url(#' + fill + ')"/><polyline points="' + points + '" fill="none" stroke="#0c8279" stroke-width="2.8" stroke-linejoin="round"/>';

  const axisLabels = coords.map(([x], i) => '<text x="' + x + '" y="222" text-anchor="middle">' + labels[i] + '</text>').join('');

  // Puntos con tooltip (valor y fecha) al pasar el cursor o al enfocarlos con el teclado.
  const pointsWithTooltip = coords.map(([x, y], i) => {
    const valueText = num(values[i], decimals) + ' ' + unit, dateText = fullDate.format(new Date(times[i]));
    const w = 118, h = 44, tx = Math.min(Math.max(x - w / 2, 2), 578 - w), ty = y - h - 12 < 2 ? y + 12 : y - h - 12;
    return '<g class="chart-point" tabindex="0" aria-label="' + dateText + ': ' + valueText + '"><circle class="chart-hit" cx="' + x + '" cy="' + y + '" r="14"/><circle class="chart-dot" cx="' + x + '" cy="' + y + '" r="4.5"/>' +
      '<g class="chart-tip"><rect x="' + tx + '" y="' + ty + '" width="' + w + '" height="' + h + '" rx="7"/><text class="chart-tip-value" x="' + (tx + w / 2) + '" y="' + (ty + 19) + '" text-anchor="middle">' + valueText + '</text><text class="chart-tip-date" x="' + (tx + w / 2) + '" y="' + (ty + 35) + '" text-anchor="middle">' + dateText + '</text></g></g>';
  }).join('');

  const legend = '<div class="chart-legend"><span class="line-swatch"></span> ' + name + '</div>';

  return summary + svgOpen + grid + line + axisLabels + pointsWithTooltip + '</svg>' + legend;
}
