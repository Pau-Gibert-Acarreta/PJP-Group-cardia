import { formatNumber as num, formatDate as date, riskLevel, RISK_LABELS } from './data.js';
import { icon, avatar, esc } from './ui.js';
import { getIndicatorRows, summarizeIndicator, evaluateFindings, patientKdigo } from './clinical.js';

const displayDate = point => point ? date(point.date.slice(0, 10)) : 'Sin fecha';
export function formattedValue(value, definition) { return num(value, definition.decimals); }
export function formatDelta(summary) {
  return (summary.delta > 0 ? '+' : summary.delta < 0 ? '−' : '') + num(Math.abs(summary.delta), summary.decimals);
}
export function overviewHeader(config, sort) {
  return '<thead><tr><th scope="col"><button data-action="sort-risk">Prob. riesgo ' + icon(sort === 'risk-asc' ? 'arrowUp' : 'arrowDown') + '</button></th><th scope="col">Paciente</th><th scope="col"><abbr title="Categorías de eGFR y albuminuria. No equivale a un diagnóstico.">KDIGO</abbr><small>eGFR / ACR</small></th>' +
    config.overviewFields.map(field => {
      const definition = config.indicators.find(item => item.field === field);
      return '<th scope="col">' + esc(definition.shortLabel || definition.label) + '<small>' + esc(definition.unit) + '</small></th>';
    }).join('') + '<th scope="col">Fecha última<br>prueba</th><th scope="col"><span class="sr-only">Ver ficha</span></th></tr></thead>';
}
export function overviewRow(p, config) {
  const level = riskLevel(p.risk), kdigo = patientKdigo(p, config);
  return '<tr data-patient-row="' + p.id + '"><td><div class="overview-risk ' + level + '"><strong>' + num(p.risk, 1) + '<span> %</span></strong><span><i class="dot"></i>' + RISK_LABELS[level] + '</span></div></td><td><div class="patient-cell">' + avatar(p) + '<div><a class="patient-link" href="#paciente/' + p.id + '">' + esc(p.name) + '</a><small class="patient-demographics">' + p.age + ' años · ' + esc(p.sex) + '</small></div></div></td><td><span class="kdigo-value" title="Categorías de las últimas mediciones disponibles; no establece diagnóstico de ERC">' + (kdigo || 'Sin datos') + '</span></td>' +
    config.overviewFields.map(field => {
      const summary = summarizeIndicator(p, config.indicators.find(item => item.field === field));
      return '<td class="overview-numeric"><span title="' + (summary.latest ? 'Medición: ' + displayDate(summary.latest) : 'Sin mediciones disponibles') + '">' + (summary.latest ? formattedValue(summary.latest.value, summary) : '<span class="missing-value">—</span>') + '</span></td>';
    }).join('') + '<td><time class="test-date" datetime="' + p.lastTest + '">' + date(p.lastTest) + '</time></td><td><a class="row-arrow" href="#paciente/' + p.id + '" aria-label="Abrir ficha de ' + esc(p.name) + '">' + icon('chevron') + '</a></td></tr>';
}
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
    coords.map(([x, y], index) => '<circle cx="' + x + '" cy="' + y + '" r="' + (index === series.length - 1 ? '3.3' : '2.2') + '" fill="' + (index === series.length - 1 ? 'currentColor' : 'white') + '" stroke="currentColor" stroke-width="1.4"><title>' + esc(displayDate(series[index]) + ' · ' + formattedValue(series[index].value, summary) + ' ' + summary.unit) + '</title></circle>').join('') +
    '</svg><div class="trend-range"><span>mín ' + formattedValue(min, summary) + '</span><span>máx ' + formattedValue(max, summary) + '</span></div></div>';
}
export function renderIndicators(patient, config) {
  const rows = getIndicatorRows(patient, config);
  return '<section class="card key-indicators-card" aria-labelledby="key-indicators-title"><div class="section-heading"><div><h2 id="key-indicators-title">' + icon('activity') + ' Indicadores clave <span class="count-pill">' + rows.length + '</span></h2><p>Últimos valores e historial de cada indicador, independientes de la predicción.</p></div><span class="subtle-label">Cada tendencia utiliza su propio mínimo y máximo</span></div><div class="indicator-table-scroll" role="region" aria-label="Indicadores con historial, desplazables horizontalmente" tabindex="0"><table class="indicator-table"><thead><tr><th scope="col">Indicador</th><th scope="col">Último valor</th><th scope="col">Fecha del valor</th><th scope="col">Tendencia <span class="table-heading-hint">mín → máx</span></th><th scope="col">Cambio anterior</th></tr></thead><tbody>' +
    rows.map(summary => '<tr data-indicator="' + esc(summary.field) + '"><th scope="row">' + esc(summary.label) + '</th><td class="indicator-latest">' + (summary.latest ? '<strong>' + formattedValue(summary.latest.value, summary) + '</strong><span>' + esc(summary.unit) + '</span>' : '<span class="missing-value">Sin datos</span>') + '</td><td>' + (summary.latest ? '<time datetime="' + esc(summary.latest.date) + '">' + displayDate(summary.latest) + '</time>' : '<span class="missing-value">—</span>') + '</td><td>' + indicatorTrend(summary) + '</td><td><span class="indicator-change ' + (summary.delta === 0 ? 'unchanged' : '') + '">' + icon(summary.delta > 0 ? 'arrowUp' : summary.delta < 0 ? 'arrowDown' : 'activity') + formatDelta(summary) + ' <small>' + esc(summary.unit) + '</small></span><small class="comparison-date">' + (summary.previous ? 'Frente a ' + displayDate(summary.previous) : summary.latest ? 'Sin valor anterior' : 'Sin mediciones') + '</small></td></tr>').join('') +
    '</tbody></table></div><p class="indicator-footnote">El cambio se calcula frente a la medición anterior. Sin una medición comparable se muestra 0.</p></section>';
}
export function renderFindings(patient, config, ruleConfig) {
  const findings = evaluateFindings(patient, config, ruleConfig);
  return '<section class="card findings-card" aria-labelledby="findings-title"><div class="section-heading"><div><h2 id="findings-title">' + icon('bell') + ' Hallazgos activos <span class="count-pill">' + findings.length + '</span></h2><p>Cambios entre las dos últimas mediciones.</p></div></div><div class="findings-list">' +
    (findings.length ? findings.map(finding => {
      const summary = finding.indicator;
      return '<article class="finding ' + finding.severity + '" data-rule-id="' + esc(finding.id) + '"><div class="finding-heading"><span class="finding-marker"></span><h3>' + esc(finding.title) + '</h3><span class="finding-delta">' + formatDelta(summary) + ' ' + esc(summary.unit) + '</span></div><div class="finding-comparison"><div><span>Anterior</span><strong>' + formattedValue(summary.previous.value, summary) + ' <small>' + esc(summary.unit) + '</small></strong><time datetime="' + esc(summary.previous.date) + '">' + displayDate(summary.previous) + '</time></div><span class="finding-arrow">' + icon('chevron') + '</span><div><span>Actual</span><strong>' + formattedValue(summary.latest.value, summary) + ' <small>' + esc(summary.unit) + '</small></strong><time datetime="' + esc(summary.latest.date) + '">' + displayDate(summary.latest) + '</time></div></div></article>';
    }).join('') : '<div class="findings-empty">' + icon('check') + '<h3>Sin cambios que activen alertas</h3><p>Las mediciones disponibles no cumplen las reglas de cambio configuradas. Los indicadores sin historial comparable no generan hallazgos.</p></div>') +
    '</div><p class="finding-footnote">' + icon('info') + ' Alertas de demostración pendientes de validación clínica.</p></section>';
}

