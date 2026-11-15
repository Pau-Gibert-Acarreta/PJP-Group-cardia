// Vista de la ficha del paciente. Cada sección de la pantalla es una función propia.
import { state, clinical } from '../../app/state.js';
import { notesFor } from '../../services/notes-service.js';
import { riskLevel, effectiveRiskLevel, isRiskOverridden, RISK_LABELS } from '../../domain/risk.js';
import { formatNumber as num, formatDate as date } from '../../utils/format.js';
import { esc } from '../../utils/text.js';
import { $ } from '../dom.js';
import { icon } from '../icons.js';
import { avatar } from '../components/avatar.js';
import { riskBadge } from '../components/risk-badge.js';
import { chartPicker, chart } from '../components/chart.js';
import { renderFindings } from '../components/findings-card.js';
import { renderIndicators } from '../components/key-indicators.js';
import { similarCasesCard, similarCasesBody } from '../components/similar-cases.js';
import { cachedSimilar, loadSimilar } from '../../services/similar-service.js';
import { currentPatientId } from '../../app/router.js';

function pageHeading(p) {
  return '<section class="page-heading patient-page-heading"><div><a class="back-link" href="#">' + icon('arrow') + ' Volver a pacientes</a>' +
    '<h1>Una visión completa de ' + p.firstName + '</h1><p>La información relevante, conectada en un mismo lugar.</p></div>' +
    '<button class="button ' + (p.followup ? 'soft' : 'primary') + '" data-action="followup" data-id="' + p.id + '">' + icon(p.followup ? 'check' : 'bookmark') + (p.followup ? 'En seguimiento' : 'Añadir a seguimiento') + '</button></section>';
}

// Datos personales, antecedentes y contacto.
function identityCard(p) {
  return '<section class="card identity-card"><div class="identity-top">' + avatar(p, true) +
    '<div><span class="eyebrow">FICHA DEL PACIENTE</span><h2>' + p.name + '</h2><p>' + p.age + ' años <span>·</span> ' + p.sex + '</p><span class="patient-id">' + p.cip + '</span></div></div>' +
    '<div class="conditions-label">Antecedentes relevantes</div>' +
    '<div class="condition-chips">' + (p.conditions.length ? p.conditions.map(c => '<span>' + c + '</span>').join('') : '<span>Sin antecedentes registrados</span>') + '</div>' +
    '<div class="contact-grid"><div>' + icon('phone') + '<span><small>Teléfono de contacto</small>' + p.phone + '</span></div><div>' + icon('mail') + '<span><small>Correo electrónico</small>' + esc(p.email) + '</span></div></div>' +
    '<div class="identity-footer">' + icon('clock') + ' Últimos datos: ' + date(p.lastTest) + '</div></section>';
}

// Clasificación final con su etiqueta, marca de ajuste y botón para ajustarla.
function riskClassification(p) {
  const overridden = isRiskOverridden(p);
  return '<div class="risk-classification">' + riskBadge(effectiveRiskLevel(p)) +
    (overridden ? '<span class="override-tag">' + icon('edit') + 'Ajustada</span>' : '') +
    '<button class="text-button adjust-risk" data-action="edit-risk">' + icon('edit') + (overridden ? 'Cambiar' : 'Ajustar') + '</button></div>';
}

// Quién ajustó la clasificación, cuándo, qué decía el modelo y por qué.
function overrideNote(p) {
  if (!isRiskOverridden(p)) return '';
  const o = p.riskOverride;
  return '<div class="override-note">' + icon('edit') + '<div><strong>Clasificación ajustada por ' + esc(o.author || 'el médico') + '</strong>' +
    '<span>Modelo: ' + RISK_LABELS[riskLevel(p.risk)] + ' (' + num(p.risk, 1) + ' %) · ' + date(o.date.slice(0, 10)) + '</span>' +
    (o.reason ? '<p>' + esc(o.reason) + '</p>' : '') + '</div></div>';
}

// Riesgo cardiovascular estimado y variables que lo explican.
function predictionCard(p) {
  const hasRisk = Number.isFinite(p.risk);
  const gauge = '<div class="risk-gauge ' + (hasRisk ? riskLevel(p.risk) : '') + '"><svg viewBox="0 0 110 110" aria-hidden="true"><circle class="gauge-bg" cx="55" cy="55" r="45"/><circle class="gauge-value" cx="55" cy="55" r="45" pathLength="100" stroke-dasharray="' + (hasRisk ? p.risk : 0) + ' 100"/></svg>' +
    '<div><strong>' + (hasRisk ? num(p.risk, 1) + '<small>%</small>' : '—') + '</strong><span>probabilidad</span></div></div>';
  const topK = '<label>Top <select id="top-k" aria-label="Número de variables explicativas"><option value="3" ' + (state.topK === 3 ? 'selected' : '') + '>3</option><option value="5" ' + (state.topK === 5 ? 'selected' : '') + '>5</option></select></label>';
  // Contribución SHAP: la barra es su peso relativo y la flecha, si sube o baja el riesgo de este paciente.
  const factors = p.factors.slice(0, state.topK).map(f => '<div class="factor ' + (f.direction === 'down' ? 'reduces' : 'raises') + '" title="' + (f.direction === 'down' ? 'Reduce' : 'Aumenta') + ' el riesgo estimado"><span>' + esc(f.label) + ' <em class="factor-direction">' + (f.direction === 'down' ? '↓' : '↑') + '</em></span><div class="factor-track"><i style="width:' + f.weight + '%"></i></div><strong>' + esc(f.value) + '</strong></div>').join('');
  return '<section class="card prediction-card"><div class="section-heading"><h2>Riesgo cardiovascular</h2><button class="icon-button small" data-action="risk-info" aria-label="Información sobre el riesgo">' + icon('info') + '</button></div>' +
    '<div class="prediction-overview">' + gauge + '<div>' + riskClassification(p) + '<h3>Estimación a 10 años</h3><p>Probabilidad de un evento cardiovascular<br>según el modelo de Cox (Framingham).</p></div></div>' +
    overrideNote(p) +
    '<div class="factors-heading"><h3>Variables que explican la estimación</h3>' + topK + '</div>' +
    '<div class="factors">' + factors + '</div><p class="factor-caption">Contribución de cada variable a esta estimación (SHAP): ↑ aumenta y ↓ reduce el riesgo. No implica causalidad.</p></section>';
}

// Línea de tiempo de la historia cardiovascular.
function timelineCard(p) {
  return '<section class="card timeline-card"><div class="section-heading"><div><h2>' + icon('clock') + ' Historia cardiovascular</h2><p>Pruebas y acontecimientos relevantes en el tiempo.</p></div>' +
    '<span class="subtle-label">Selecciona un evento para consultarlo ' + icon('chevron') + '</span></div>' +
    '<div class="timeline">' + p.events.map((e, i) =>
      '<button class="timeline-event ' + (i === p.events.length - 1 ? 'latest' : '') + '" data-action="event" data-event="' + e.id + '"><span class="event-date">' + date(e.date) + '</span><span class="event-marker">' + icon(e.icon) + '</span><strong>' + e.title + '</strong><span class="event-type">' + e.type + (e.documentId ? ' · con informe' : '') + '</span></button>').join('') +
    '</div></section>';
}

// Gráfica "Evolución de indicadores" con pestañas y selector de periodo.
function chartCard(p) {
  return '<section class="card chart-card"><div class="section-heading"><div><h2>Evolución de indicadores</h2><p>Una perspectiva de los cambios en el tiempo.</p></div>' +
    '<button class="icon-button small" data-action="expand-chart" aria-label="Ampliar gráfica">' + icon('expand') + '</button></div>' +
    '<div class="chart-toolbar"><div class="chart-picker-slot">' + chartPicker(p, state) + '</div>' +
    '<label class="period-select"><select id="chart-period" aria-label="Periodo de la gráfica"><option value="6" ' + (state.period === '6' ? 'selected' : '') + '>6 meses</option><option value="12" ' + (state.period === '12' ? 'selected' : '') + '>12 meses</option><option value="all" ' + (state.period === 'all' ? 'selected' : '') + '>Todo el historial</option></select>' + icon('down') + '</label></div>' +
    '<div id="chart-content">' + chart(p, state) + '</div></section>';
}

export function noteDate(value) {
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(d);
}

// Notas de consulta: listado y editor.
function notesCard(p) {
  const notes = notesFor(p);
  const list = notes.map(n => '<article class="clinical-note"><div class="note-header"><span class="note-avatar">CV</span><div><strong>' + esc(n.author) + '</strong><time>' + noteDate(n.date) + '</time></div>' +
    (!n.id.startsWith('seed-') ? '<button class="text-button" data-action="edit-note" data-note="' + esc(n.id) + '">Editar</button>' : '') + '</div><p>' + esc(n.text) + '</p></article>').join('');
  const editor = '<form id="note-form" class="note-editor"><label for="note-text">' + (state.noteEditing ? 'Editar nota' : 'Añadir una nota') + '</label>' +
    '<textarea id="note-text" required maxlength="2000" rows="5" placeholder="Escribe tus observaciones de la consulta…">' + esc(state.drafts[p.id] || '') + '</textarea>' +
    '<div class="editor-footer"><small id="note-counter">' + (state.drafts[p.id]?.length || 0) + '/2000</small>' +
    (state.noteEditing ? '<button type="button" class="text-button" data-action="cancel-note">Cancelar</button>' : '') +
    '<button class="button primary" type="submit">' + icon('plus') + (state.noteEditing ? 'Guardar cambios' : 'Guardar nota') + '</button></div>' +
    '<small class="privacy-hint">Usa únicamente información ficticia en esta demo.</small></form>';
  return '<section class="card notes-card" id="clinical-notes"><div class="section-heading"><div><h2>' + icon('note') + ' Notas de consulta <span class="count-pill">' + notes.length + '</span></h2><p>Tu contexto clínico también forma parte de la historia.</p></div>' +
    '<span class="local-label">' + icon('shield') + ' Guardadas en la historia clínica</span></div>' +
    '<div class="notes-layout"><div class="notes-list">' + list + '</div>' + editor + '</div></section>';
}

export function renderPatient(p) {
  $('#main-content').innerHTML = pageHeading(p) +
    '<div class="patient-top-grid">' + identityCard(p) + predictionCard(p) + '</div>' +
    timelineCard(p) +
    '<div class="clinical-grid">' + chartCard(p) + renderFindings(p, clinical.config, clinical.ruleConfig) + '</div>' +
    similarCasesCard(state.knnIncludeLatest, { loading: true }) +
    '<div class="detail-bottom-grid">' + renderIndicators(p, clinical.config) + notesCard(p) + '</div>';
  mountSimilarCases(p);
}

// Casos similares (KNN): se piden al pintar la ficha y se rellenan al llegar.
// Sin la última prueba al abrir el paciente; con ella cuando el médico lo elige.
export function mountSimilarCases(p) {
  const includeLatest = state.knnIncludeLatest;
  const fill = result => {
    const slot = $('#similar-cases-body');
    if (!slot || currentPatientId() !== p.id || state.knnIncludeLatest !== includeLatest) return;
    slot.innerHTML = similarCasesBody(result.data ? { data: result.data } : {
      error: result.status === 409 ? result.error + '. Prueba con «Con la última prueba».' : 'No se pueden cargar los casos similares: ' + result.error
    });
  };
  const cached = cachedSimilar(p.id, includeLatest);
  if (cached) cached.then(fill); else loadSimilar(p.id, includeLatest).then(fill);
}
