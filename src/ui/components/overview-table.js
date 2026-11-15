// Tabla del listado de pacientes: cabecera, filas y minigráfica de tendencia de eGFR.
// Las columnas de indicadores salen de config/indicators.json (overviewFields).
import { formatNumber as num, formatDate as date } from '../../utils/format.js';
import { esc } from '../../utils/text.js';
import { riskLevel, effectiveRiskLevel, isRiskOverridden, RISK_LABELS } from '../../domain/risk.js';
import { summarizeIndicator } from '../../domain/measurements.js';
import { patientKdigo } from '../../domain/kdigo.js';
import { egfrLevel, valueTone } from '../../domain/indicator-status.js';
import { displayDate, formattedValue } from '../formatters.js';
import { icon } from '../icons.js';
import { avatar } from './avatar.js';

export function overviewHeader(config, sort) {
  return '<thead><tr>' +
    '<th scope="col"><button data-action="sort-risk">Prob. riesgo ' + icon(sort === 'risk-asc' ? 'arrowUp' : 'arrowDown') + '</button></th>' +
    '<th scope="col" class="egfr-trend-head">Tendencia eGFR<small>mL/min/1,73 m²</small></th>' +
    '<th scope="col">Paciente</th>' +
    '<th scope="col"><abbr title="Categorías de eGFR y albuminuria. No equivale a un diagnóstico.">KDIGO</abbr><small>eGFR / ACR</small></th>' +
    config.overviewFields.map(field => {
      const definition = config.indicators.find(item => item.field === field);
      return '<th scope="col">' + esc(definition.shortLabel || definition.label) + '<small>' + esc(definition.unit) + '</small></th>';
    }).join('') +
    '<th scope="col">Fecha última<br>prueba</th>' +
    '<th scope="col"><span class="sr-only">Ver ficha</span></th>' +
    '</tr></thead>';
}

export function overviewRow(p, config) {
  const level = effectiveRiskLevel(p), kdigo = patientKdigo(p, config);
  return '<tr data-patient-row="' + p.id + '">' +
    '<td><div class="overview-risk ' + level + '"><strong>' + (Number.isFinite(p.risk) ? num(p.risk, 1) + '<span> %</span>' : '—') + '</strong><span><i class="dot"></i>' + RISK_LABELS[level] + (isRiskOverridden(p) ? '<span class="override-mark" title="Clasificación ajustada por el médico. Modelo: ' + RISK_LABELS[riskLevel(p.risk)] + '">' + icon('edit') + '</span>' : '') + '</span></div></td>' +
    '<td>' + egfrTrendCell(p, config) + '</td>' +
    '<td><div class="patient-cell">' + avatar(p) + '<div><a class="patient-link" href="#paciente/' + p.id + '">' + esc(p.name) + '</a><small class="patient-demographics">' + p.age + ' años · ' + esc(p.sex) + '</small></div></div></td>' +
    '<td><span class="kdigo-value" title="Categorías de las últimas mediciones disponibles; no establece diagnóstico de ERC">' + (kdigo || 'Sin datos') + '</span></td>' +
    config.overviewFields.map(field => {
      const summary = summarizeIndicator(p, config.indicators.find(item => item.field === field));
      return '<td class="overview-numeric"><span title="' + (summary.latest ? 'Medición: ' + displayDate(summary.latest) : 'Sin mediciones disponibles') + '">' +
        (summary.latest ? formattedValue(summary.latest.value, summary) : '<span class="missing-value">—</span>') + '</span></td>';
    }).join('') +
    '<td><time class="test-date" datetime="' + p.lastTest + '">' + date(p.lastTest) + '</time></td>' +
    '<td><a class="row-arrow" href="#paciente/' + p.id + '" aria-label="Abrir ficha de ' + esc(p.name) + '">' + icon('chevron') + '</a></td>' +
    '</tr>';
}

// Último eGFR con su color y la minigráfica de su historial.
export function egfrTrendCell(patient, config) {
  const definition = config.indicators.find(item => item.field === config.kdigoFields?.egfr);
  if (!definition) return '<span class="missing-value">—</span>';
  const summary = summarizeIndicator(patient, definition), { series, min, max } = summary;
  if (!series.length) return '<span class="missing-value">Sin datos</span>';
  const latest = summary.latest.value;
  const level = valueTone(latest, definition) !== 'neutral'
    ? valueTone(latest, definition)
    : ({ ok: 'green', mild: 'yellow', moderate: 'orange', severe: 'red' })[egfrLevel(latest)];
  const first = series[0].time, last = series.at(-1).time;
  const coords = series.map(point => [
    first === last ? 36 : 3 + (point.time - first) / (last - first) * 66,
    min === max ? 13 : 22 - (point.value - min) / (max - min) * 18
  ]);
  const label = 'eGFR. ' + series.map(point => displayDate(point) + ': ' + formattedValue(point.value, summary)).join('; ');
  const [lx, ly] = coords.at(-1);
  return '<div class="egfr-trend tone-' + level + '" title="' + esc(label) + '"><span class="egfr-dot"></span><strong>' + formattedValue(latest, summary) + '</strong>' +
    '<svg viewBox="0 0 72 26" role="img" aria-label="' + esc(label) + '">' +
    (series.length > 1 ? '<polyline points="' + coords.map(point => point.map(n => n.toFixed(1)).join(',')).join(' ') + '" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' : '') +
    '<circle cx="' + lx.toFixed(1) + '" cy="' + ly.toFixed(1) + '" r="3" fill="currentColor"/></svg></div>';
}
