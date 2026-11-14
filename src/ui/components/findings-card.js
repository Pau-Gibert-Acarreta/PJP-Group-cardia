// Sección "Hallazgos activos": cambios entre las dos últimas mediciones que cumplen las reglas configuradas.
import { esc } from '../../utils/text.js';
import { evaluateFindings } from '../../domain/findings.js';
import { changeDirection, deltaTone } from '../../domain/indicator-status.js';
import { displayDate, formattedValue, formatDelta } from '../formatters.js';
import { icon } from '../icons.js';

// Variación compacta: flecha, valor y unidad, coloreada según si mejora o empeora.
function deltaBadge(summary) {
  const direction = changeDirection(summary);
  return '<span class="finding-delta tone-' + deltaTone(summary) + '" title="' + (direction === 'worse' ? 'Empeora' : direction === 'better' ? 'Mejora' : 'Sin cambio') + ' respecto a la medición anterior">' +
    (summary.delta ? icon(summary.delta > 0 ? 'arrowUpright' : 'arrowDownright') : '<b class="delta-flat">–</b>') +
    formatDelta(summary) + ' <small>' + esc(summary.unit) + '</small></span>';
}

function comparisonValue(label, point, summary) {
  return '<div><span>' + label + '</span><strong>' + formattedValue(point.value, summary) + ' <small>' + esc(summary.unit) + '</small></strong>' +
    '<time datetime="' + esc(point.date) + '">' + displayDate(point) + '</time></div>';
}

function findingItem(finding) {
  const summary = finding.indicator;
  return '<article class="finding ' + finding.severity + '" data-rule-id="' + esc(finding.id) + '">' +
    '<div class="finding-heading"><span class="finding-marker"></span><h3>' + esc(finding.title) + '</h3>' + deltaBadge(summary) + '</div>' +
    '<div class="finding-comparison">' + comparisonValue('Anterior', summary.previous, summary) + '<span class="finding-arrow">' + icon('chevron') + '</span>' + comparisonValue('Actual', summary.latest, summary) + '</div>' +
    '</article>';
}

const emptyFindings = '<div class="findings-empty">' + icon('check') + '<h3>Sin cambios que activen alertas</h3>' +
  '<p>Las mediciones disponibles no cumplen las reglas de cambio configuradas. Los indicadores sin historial comparable no generan hallazgos.</p></div>';

export function renderFindings(patient, config, ruleConfig) {
  const findings = evaluateFindings(patient, config, ruleConfig);
  return '<section class="card findings-card" aria-labelledby="findings-title">' +
    '<div class="section-heading"><div><h2 id="findings-title">' + icon('bell') + ' Hallazgos activos <span class="count-pill">' + findings.length + '</span></h2><p>Cambios entre las dos últimas mediciones.</p></div></div>' +
    '<div class="findings-list">' + (findings.length ? findings.map(findingItem).join('') : emptyFindings) + '</div>' +
    '<p class="finding-footnote">' + icon('info') + ' Alertas de demostración pendientes de validación clínica.</p></section>';
}
