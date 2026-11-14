import { patients, riskLevel, RISK_LABELS, formatNumber as num, formatDate as date, selectPatients } from './data.js';
import { icon, avatar, esc } from './ui.js';
import { chartTabs, chartData, chart } from './charts.js';
import { loadClinicalConfig, summarizeIndicator, patientKdigo, getSeries } from './clinical.js';
import { overviewHeader, overviewRow, renderIndicators, renderFindings } from './clinical-ui.js';
let clinicalConfig, ruleConfig;
const $ = selector => document.querySelector(selector);
const defaults = () => ({ search: '', risk: 'all', sex: 'all', condition: 'all', age: 'all', followupOnly: false, sort: 'risk-desc' });
const state = { filters: defaults(), page: 1, perPage: 8, nav: 'patients', topK: 3, chart: 'ldl', period: '12', drafts: {}, noteEditing: null };
let storageAvailable = true;
function readStorage(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { storageAvailable = false; return fallback; } }
function saveStorage(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { storageAvailable = false; return false; } }
const storedFollowups = readStorage('cardia.followups', {});
patients.forEach(p => { if (typeof storedFollowups?.[p.id] === 'boolean') p.followup = storedFollowups[p.id]; });
const storedNotes = readStorage('cardia.notes', {});
const savedNotes = storedNotes && typeof storedNotes === 'object' && !Array.isArray(storedNotes) ? storedNotes : {};
const currentPatient = () => patients.find(p => p.id === location.hash.match(/^#paciente\/([^/]+)$/)?.[1]);
const badge = p => '<span class="risk-badge ' + riskLevel(p.risk) + '"><span class="dot"></span>' + RISK_LABELS[riskLevel(p.risk)] + '</span>';
function shell() {
  const p = currentPatient();
  $('#app').innerHTML = '<aside class="sidebar"><a class="brand" href="#" aria-label="Cardia, inicio"><span class="brand-symbol">' + icon('activity') + '</span><span>cardia<span class="brand-dot">.</span></span></a>' +
    '<div class="workspace"><span class="workspace-icon">' + icon('building') + '</span><div><strong>CAP Sant Martí</strong><small>Atención primaria</small></div><span class="online-dot"></span></div>' +
    '<div class="nav-label">ESPACIO CLÍNICO</div><nav aria-label="Navegación principal">' +
    '<button class="nav-item ' + (state.nav === 'patients' ? 'active' : '') + '" data-action="nav" data-nav="patients">' + icon('users') + '<span>Pacientes</span><span class="nav-count">24</span></button>' +
    '<button class="nav-item ' + (state.nav === 'priority' ? 'active' : '') + '" data-action="nav" data-nav="priority">' + icon('heart') + '<span>Prioridad clínica</span><span class="priority-count">7</span></button>' +
    '<button class="nav-item ' + (state.nav === 'followup' ? 'active' : '') + '" data-action="nav" data-nav="followup">' + icon('bookmark') + '<span>En seguimiento</span></button></nav>' +
    '<div class="sidebar-bottom"><div class="demo-card"><span class="demo-card-icon">' + icon('flask') + '</span><strong>Un primer paso para<br>cuidar mejor.</strong><p>Prototipo para la hackathon.<br>Todos los datos son ficticios.</p><button data-action="about">Acerca de la demo ' + icon('arrowUp') + '</button></div><div class="sidebar-footer"><span class="tiny-dot"></span> Entorno de demostración <span>v0.1</span></div></div></aside>' +
    '<div class="main-shell"><header class="topbar"><div class="breadcrumb"><span>Área clínica</span>' + icon('chevron') + (p ? '<a href="#">Pacientes</a>' + icon('chevron') + '<strong>Ficha del paciente</strong>' : '<strong>Pacientes</strong>') + '</div>' +
    '<div class="topbar-right"><span class="demo-pill"><span></span> Demo · datos ficticios</span><span class="topbar-divider"></span><button class="icon-button notification" aria-label="Ver avisos de la demo" data-action="notifications">' + icon('bell') + '<i></i></button><button class="doctor" data-action="profile"><span class="doctor-avatar">CV</span><span><strong>Dra. Carmen Vidal</strong><small>Medicina de familia</small></span>' + icon('down') + '</button></div></header><main id="main-content" class="content"></main><footer class="page-footer"><span>Cardia · Una visión más completa del paciente</span><span>' + icon('shield') + ' Prototipo con datos sintéticos</span></footer></div>';
  if (p) renderPatient(p); else if (location.hash.startsWith('#paciente/')) renderNotFound(); else renderList();
}
function renderList() {
  const [title, subtitle] = state.nav === 'priority' ? ['Prioridad clínica', 'Una mirada a los pacientes con mayor riesgo cardiovascular.'] : state.nav === 'followup' ? ['Pacientes en seguimiento', 'Tu selección de pacientes para seguir su evolución de cerca.'] : ['Tus pacientes, de un vistazo', 'Detecta señales, conecta la información y prioriza la atención.'];
  $('#main-content').innerHTML = '<section class="page-heading"><div><div class="eyebrow">VISIÓN GLOBAL</div><h1>' + title + '</h1><p>' + subtitle + '</p></div><div class="date-label">' + icon('calendar') + ' 14 de noviembre de 2026</div></section><section class="stats-grid" aria-label="Resumen del cupo">' +
    statCard('all', 'Total de pacientes', patients.length, 'En tu cupo de demostración', 'users') +
    statCard('high', 'Riesgo alto', patients.filter(p => riskLevel(p.risk) === 'high').length, 'Prioriza su revisión', 'heart') +
    statCard('medium', 'Riesgo medio', patients.filter(p => riskLevel(p.risk) === 'medium').length, 'Observa su evolución', 'activity') +
    statCard('low', 'Riesgo bajo', patients.filter(p => riskLevel(p.risk) === 'low').length, 'Seguimiento habitual', 'shield') + '</section>' +
    '<section class="patient-panel"><div class="panel-heading"><div><h2>Listado de pacientes <span class="count-pill" id="result-count">24</span></h2><p>La información que necesitas para saber por dónde empezar.</p></div><button class="button secondary export-button" data-action="export">' + icon('download') + ' Exportar listado</button></div>' +
    '<div class="list-tabs"><button data-action="tab" data-tab="all" class="' + (!state.filters.followupOnly ? 'selected' : '') + '">Todos los pacientes <span>24</span></button><button data-action="tab" data-tab="followup" class="' + (state.filters.followupOnly ? 'selected' : '') + '">En seguimiento <span id="followup-count">' + patients.filter(p => p.followup).length + '</span></button></div>' +
    '<div class="toolbar"><label class="search-field">' + icon('search') + '<input id="patient-search" type="search" placeholder="Buscar por nombre o identificador…" aria-label="Buscar pacientes" value="' + esc(state.filters.search) + '"></label>' +
    '<details class="filter-dropdown"><summary class="button secondary">' + icon('filter') + ' Filtros <span id="filter-number"></span></summary><div class="filter-popover"><div class="popover-heading"><strong>Filtrar pacientes</strong><button class="text-button" data-action="clear">Restablecer</button></div>' +
    filterSelect('risk', 'Riesgo cardiovascular', [['all', 'Todos los niveles'], ['high', 'Alto · ≥ 20 %'], ['medium', 'Medio · 10 a < 20 %'], ['low', 'Bajo · < 10 %']]) +
    filterSelect('sex', 'Sexo', [['all', 'Todos'], ['Mujer', 'Mujer'], ['Hombre', 'Hombre']]) +
    filterSelect('age', 'Edad', [['all', 'Todas las edades'], ['under65', 'Menores de 65 años'], ['65plus', '65 años o más']]) +
    filterSelect('condition', 'Antecedentes', [['all', 'Todos los antecedentes'], ...['Hipertensión', 'Diabetes tipo 2', 'Enf. renal crónica', 'Dislipidemia', 'Tabaquismo'].map(x => [x, x])]) +
    '<small>Umbrales ilustrativos, solo para esta demo.</small><button class="button primary full-width" data-action="close-filters">Ver resultados</button></div></details>' +
    '<label class="sort-select">' + icon('sort') + '<select id="sort" aria-label="Ordenar pacientes">' + [['risk-desc', 'Mayor riesgo primero'], ['risk-asc', 'Menor riesgo primero'], ['name', 'Nombre: A–Z'], ['age', 'Mayor edad primero'], ['recent', 'Analítica más reciente']].map(([v, t]) => '<option value="' + v + '" ' + (state.filters.sort === v ? 'selected' : '') + '>' + t + '</option>').join('') + '</select></label></div><div id="active-filters" class="active-filters"></div><div id="patient-results"></div></section>' +
    '<div class="legend"><span class="legend-label">Semáforo de riesgo</span><span><i class="dot low"></i> Bajo &lt; 10 %</span><span><i class="dot medium"></i> Medio 10–&lt;20 %</span><span><i class="dot high"></i> Alto ≥ 20 %</span><button data-action="risk-info">' + icon('info') + ' ¿Cómo se interpreta?</button></div>';
  updateResults();
}
function statCard(level, label, count, caption, glyph) {
  return '<button class="stat-card ' + level + '" data-action="risk-filter" data-risk="' + level + '"><div class="stat-title">' + label + '<span class="stat-icon">' + icon(glyph) + '</span></div><div class="stat-value">' + count + '<span>pacientes</span></div><div class="stat-caption">' + (level !== 'all' ? '<span class="dot"></span>' : '') + caption + '</div></button>';
}
function filterSelect(key, label, options) {
  return '<label class="form-label">' + label + '<select data-filter="' + key + '">' + options.map(([v, t]) => '<option value="' + v + '" ' + (state.filters[key] === v ? 'selected' : '') + '>' + t + '</option>').join('') + '</select></label>';
}
function updateResults() {
  const items = selectPatients(patients, state.filters);
  state.page = Math.max(1, Math.min(state.page, Math.ceil(items.length / state.perPage)));
  const start = (state.page - 1) * state.perPage;
  $('#result-count').textContent = items.length; $('#followup-count').textContent = patients.filter(p => p.followup).length;
  document.querySelectorAll('.stat-card').forEach(el => { const selected = el.dataset.risk === state.filters.risk; el.classList.toggle('stat-selected', selected); el.setAttribute('aria-pressed', selected); });
  document.querySelectorAll('.list-tabs button').forEach(el => el.classList.toggle('selected', (el.dataset.tab === 'followup') === state.filters.followupOnly));
  const filters = ['risk', 'sex', 'age', 'condition'].filter(k => state.filters[k] !== 'all');
  $('#filter-number').textContent = filters.length ? filters.length : '';
  const labels = { risk: 'Riesgo ' + (RISK_LABELS[state.filters.risk] || ''), sex: state.filters.sex, age: state.filters.age === '65plus' ? '≥ 65 años' : '< 65 años', condition: state.filters.condition };
  $('#active-filters').innerHTML = filters.map(k => '<button class="filter-chip" data-action="remove-filter" data-filter="' + k + '">' + esc(labels[k]) + icon('close') + '</button>').join('') + (filters.length ? '<button class="text-button" data-action="clear">Limpiar filtros</button>' : '');
  document.querySelectorAll('select[data-filter]').forEach(el => el.value = state.filters[el.dataset.filter]);
  $('#patient-results').innerHTML = items.length ? '<div class="table-scroll" role="region" aria-label="Listado con indicadores clínicos, desplazable horizontalmente" tabindex="0"><table class="patient-table overview-table">' + overviewHeader(clinicalConfig, state.filters.sort) + '<tbody>' +
    items.slice(start, start + state.perPage).map(p => overviewRow(p, clinicalConfig)).join('') +
    '</tbody></table></div><div class="pagination"><span>Mostrando <strong>' + (start + 1) + '–' + Math.min(start + state.perPage, items.length) + '</strong> de <strong>' + items.length + '</strong> pacientes</span><div><button class="icon-button" aria-label="Página anterior" data-action="page" data-page="' + (state.page - 1) + '" ' + (state.page === 1 ? 'disabled' : '') + '>' + icon('arrow') + '</button>' + Array.from({ length: Math.ceil(items.length / state.perPage) }, (_, i) => '<button class="page-number ' + (state.page === i + 1 ? 'current' : '') + '" data-action="page" data-page="' + (i + 1) + '" aria-label="Página ' + (i + 1) + '" ' + (state.page === i + 1 ? 'aria-current="page"' : '') + '>' + (i + 1) + '</button>').join('') + '<button class="icon-button" aria-label="Página siguiente" data-action="page" data-page="' + (state.page + 1) + '" ' + (start + state.perPage >= items.length ? 'disabled' : '') + '>' + icon('chevron') + '</button></div></div>' :
    '<div class="empty-state"><span>' + icon('search') + '</span><h3>No hay pacientes con estos criterios</h3><p>Prueba con otro nombre o ajusta los filtros de búsqueda.</p><button class="button secondary" data-action="clear-all">Restablecer búsqueda y filtros</button></div>';
}

function renderPatient(p) {
  $('#main-content').innerHTML = '<section class="page-heading patient-page-heading"><div><a class="back-link" href="#">' + icon('arrow') + ' Volver a pacientes</a><h1>Una visión completa de ' + p.firstName + '</h1><p>La información relevante, conectada en un mismo lugar.</p></div><button class="button ' + (p.followup ? 'soft' : 'primary') + '" data-action="followup" data-id="' + p.id + '">' + icon(p.followup ? 'check' : 'bookmark') + (p.followup ? 'En seguimiento' : 'Añadir a seguimiento') + '</button></section>' +
    '<div class="patient-top-grid"><section class="card identity-card"><div class="identity-top">' + avatar(p, true) + '<div><span class="eyebrow">FICHA DEL PACIENTE</span><h2>' + p.name + '</h2><p>' + p.age + ' años <span>·</span> ' + p.sex + '</p><span class="patient-id">' + p.cip + '</span></div></div><div class="conditions-label">Antecedentes relevantes</div><div class="condition-chips">' + (p.conditions.length ? p.conditions.map(c => '<span>' + c + '</span>').join('') : '<span>Sin antecedentes registrados</span>') + '</div><div class="contact-grid"><div>' + icon('phone') + '<span><small>Teléfono de contacto</small>' + p.phone + '</span></div><div>' + icon('mail') + '<span><small>Correo electrónico</small>' + esc(p.email) + '</span></div></div><div class="identity-footer">' + icon('clock') + ' Últimos datos: ' + date(p.lastTest) + '<span>Datos ficticios</span></div></section>' +
    '<section class="card prediction-card"><div class="section-heading"><h2>Riesgo cardiovascular</h2><button class="icon-button small" data-action="risk-info" aria-label="Información sobre el riesgo">' + icon('info') + '</button></div><div class="prediction-overview"><div class="risk-gauge ' + riskLevel(p.risk) + '"><svg viewBox="0 0 110 110" aria-hidden="true"><circle class="gauge-bg" cx="55" cy="55" r="45"/><circle class="gauge-value" cx="55" cy="55" r="45" pathLength="100" stroke-dasharray="' + p.risk + ' 100"/></svg><div><strong>' + num(p.risk, 1) + '<small>%</small></strong><span>probabilidad</span></div></div><div>' + badge(p) + '<h3>Estimación a 10 años</h3><p>Probabilidad ficticia de un evento<br>cardiovascular para esta demostración.</p><span class="simulation-label"><i></i> Predicción simulada</span></div></div><div class="factors-heading"><h3>Variables que explican la estimación</h3><label>Top <select id="top-k" aria-label="Número de variables explicativas"><option value="3" ' + (state.topK === 3 ? 'selected' : '') + '>3</option><option value="5" ' + (state.topK === 5 ? 'selected' : '') + '>5</option></select></label></div><div class="factors">' + p.factors.slice(0, state.topK).map(f => '<div class="factor"><span>' + f.label + '</span><div class="factor-track"><i style="width:' + f.weight + '%"></i></div><strong>' + f.value + '</strong></div>').join('') + '</div><p class="factor-caption">Contribución relativa ilustrativa. No implica causalidad.</p></section></div>' +
    '<section class="card timeline-card"><div class="section-heading"><div><h2>' + icon('clock') + ' Historia cardiovascular</h2><p>Pruebas y acontecimientos relevantes en el tiempo.</p></div><span class="subtle-label">Selecciona un evento para consultarlo ' + icon('chevron') + '</span></div><div class="timeline">' + p.events.map((e, i) => '<button class="timeline-event ' + (i === p.events.length - 1 ? 'latest' : '') + '" data-action="event" data-event="' + e.id + '"><span class="event-date">' + date(e.date) + '</span><span class="event-marker">' + icon(e.icon) + '</span><strong>' + e.title + '</strong><span class="event-type">' + e.type + '</span></button>').join('') + '</div></section>' +
    '<div class="clinical-grid"><section class="card chart-card"><div class="section-heading"><div><h2>Evolución de indicadores</h2><p>Una perspectiva de los cambios en el tiempo.</p></div><button class="icon-button small" data-action="expand-chart" aria-label="Ampliar gráfica">' + icon('expand') + '</button></div><div class="chart-toolbar"><div class="chart-tabs">' + chartTabs(state) + '</div><label class="period-select"><select id="chart-period" aria-label="Periodo de la gráfica"><option value="6" ' + (state.period === '6' ? 'selected' : '') + '>6 meses</option><option value="12" ' + (state.period === '12' ? 'selected' : '') + '>12 meses</option></select>' + icon('down') + '</label></div><div id="chart-content">' + chart(p, state) + '</div></section>' +
    renderFindings(p, clinicalConfig, ruleConfig) + '</div>' + renderIndicators(p, clinicalConfig) +
    '<section class="card notes-card" id="clinical-notes"><div class="section-heading"><div><h2>' + icon('note') + ' Notas de consulta <span class="count-pill">' + notesFor(p).length + '</span></h2><p>Tu contexto clínico también forma parte de la historia.</p></div><span class="local-label">' + icon('shield') + ' Guardadas en este navegador</span></div><div class="notes-layout"><div class="notes-list">' + notesFor(p).map(n => '<article class="clinical-note"><div class="note-header"><span class="note-avatar">CV</span><div><strong>' + esc(n.author) + '</strong><time>' + noteDate(n.date) + '</time></div>' + (!n.id.startsWith('seed-') ? '<button class="text-button" data-action="edit-note" data-note="' + esc(n.id) + '">Editar</button>' : '') + '</div><p>' + esc(n.text) + '</p></article>').join('') + '</div><form id="note-form" class="note-editor"><label for="note-text">' + (state.noteEditing ? 'Editar nota' : 'Añadir una nota') + '</label><textarea id="note-text" required maxlength="2000" rows="5" placeholder="Escribe tus observaciones de la consulta…">' + esc(state.drafts[p.id] || '') + '</textarea><div class="editor-footer"><small id="note-counter">' + (state.drafts[p.id]?.length || 0) + '/2000</small>' + (state.noteEditing ? '<button type="button" class="text-button" data-action="cancel-note">Cancelar</button>' : '') + '<button class="button primary" type="submit">' + icon('plus') + (state.noteEditing ? 'Guardar cambios' : 'Guardar nota') + '</button></div><small class="privacy-hint">Usa únicamente información ficticia en esta demo.</small></form></div></section>';
}
function notesFor(p) { return [...(Array.isArray(savedNotes[p.id]) ? savedNotes[p.id].filter(n => n && typeof n.text === 'string' && typeof n.id === 'string' && typeof n.date === 'string') : []), ...p.notes].sort((a, b) => b.date.localeCompare(a.date)); }
function noteDate(value) { const d = new Date(value); return Number.isNaN(d.getTime()) ? '' : new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(d); }
function renderNotFound() { $('#main-content').innerHTML = '<div class="card empty-state"><h1>Paciente no encontrado</h1><p>El identificador no corresponde a un paciente de esta demo.</p><a class="button primary" href="#">Volver a pacientes</a></div>'; }
function openModal(title, body, wide = false) {
  const modal = $('#modal'); modal.className = wide ? 'wide-dialog' : '';
  modal.innerHTML = '<div class="modal-heading"><h2 id="modal-title">' + title + '</h2><button class="icon-button" data-action="close-modal" aria-label="Cerrar ventana">' + icon('close') + '</button></div>' + body;
  if (!modal.open) modal.showModal();
}
function openEvent(id) {
  const p = currentPatient(), e = p.events.find(e => e.id === id);
  const lab = e.type === 'Laboratorio';
  const results = clinicalConfig.indicators.filter(item => item.kind !== 'vital').map(item => ({ ...item, latest: getSeries(p, item).filter(point => point.date.slice(0, 10) <= e.date).at(-1) })).filter(item => item.latest);
  openModal(e.title, '<div class="event-dialog-meta"><span class="event-dialog-icon">' + icon(e.icon) + '</span><div><span class="eyebrow">' + e.type + '</span><p>' + date(e.date, true) + ' · ' + p.name + '</p></div></div><p class="event-description">' + e.description + '</p>' +
    (lab ? '<table class="lab-table"><thead><tr><th>Determinación</th><th>Resultado</th><th>Unidad</th></tr></thead><tbody>' + results.map(item => '<tr><td>' + esc(item.label) + '</td><td><strong>' + num(item.latest.value, item.decimals) + '</strong></td><td>' + esc(item.unit) + '</td></tr>').join('') + '</tbody></table>' :
    '<div class="event-report"><h3>Detalle del registro</h3><p>' + (id === 'ecg' ? 'Ritmo sinusal registrado a 72 lpm. Registro de ejemplo sin trazado adjunto.' : id === 'medication' ? 'Se revisan la medicación habitual, la adherencia referida y los registros de presión arterial. Nota de tratamiento ficticia para explorar el historial.' : 'Se documentan los antecedentes y se inicia el registro de indicadores para el seguimiento cardiovascular.') + '</p></div>') +
    '<div class="modal-note">' + icon('info') + ' Documento de ejemplo · resultados ficticios</div><div class="modal-footer"><button class="button primary" data-action="close-modal">Cerrar detalle</button></div>');
}
function showExpandedChart() {
  const p = currentPatient(), d = chartData(p, state);
  openModal('Evolución de ' + d.name.toLowerCase(), '<p class="dialog-subtitle">' + p.name + ' · últimos ' + state.period + ' meses</p><div class="expanded-chart">' + chart(p, state, true) + '</div><table class="lab-table"><thead><tr><th>Periodo</th><th>' + d.name + '</th></tr></thead><tbody>' + d.values.map((v, i) => '<tr><td>' + d.labels[i] + '</td><td>' + num(v, state.chart === 'hba1c' ? 1 : 0) + ' ' + d.unit + '</td></tr>').join('') + '</tbody></table>', true);
}
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('visible'); clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').classList.remove('visible'), 3500); }
function setFilter(key, value) { state.filters[key] = value; state.page = 1; updateResults(); }
function resetFilters(all = false) { const search = all ? '' : state.filters.search; state.filters = { ...defaults(), search }; state.page = 1; state.nav = 'patients'; shell(); }
function exportList() {
  const definitions = clinicalConfig.overviewFields.map(field => clinicalConfig.indicators.find(item => item.field === field));
  const rows = [['Identificador', 'Riesgo simulado (%)', 'Nivel de riesgo', 'Paciente', 'Edad', 'Sexo', 'KDIGO (eGFR / ACR)', ...definitions.map(item => item.label + ' (' + item.unit + ')'), 'Fecha última prueba'], ...selectPatients(patients, state.filters).map(p => [p.cip, num(p.risk, 1), RISK_LABELS[riskLevel(p.risk)], p.name, p.age, p.sex, patientKdigo(p, clinicalConfig) || '', ...definitions.map(item => { const latest = summarizeIndicator(p, item).latest; return latest ? num(latest.value, item.decimals) : ''; }), p.lastTest])];
  const csv = '\uFEFF' + rows.map(row => row.map(v => '"' + String(v).replaceAll('"', '""') + '"').join(';')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const a = document.createElement('a'); a.href = url; a.download = 'cardia-pacientes-demo.csv'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000); toast('Listado filtrado exportado con datos ficticios');
}

function handleAction(event) {
  const target = event.target.closest('[data-action]');
  if (!target) {
    const row = event.target.closest('[data-patient-row]');
    if (row && !event.target.closest('a,button,input,select')) location.hash = 'paciente/' + row.dataset.patientRow;
    return;
  }
  const action = target.dataset.action, p = currentPatient();
  if (action === 'retry-config') { boot(); return; }
  if (action === 'nav') {
    state.nav = target.dataset.nav; state.filters = defaults(); state.page = 1;
    if (state.nav === 'priority') state.filters.risk = 'high';
    if (state.nav === 'followup') state.filters.followupOnly = true;
    if (location.hash) location.hash = ''; else shell();
  } else if (action === 'risk-filter') setFilter('risk', state.filters.risk === target.dataset.risk && target.dataset.risk !== 'all' ? 'all' : target.dataset.risk);
  else if (action === 'tab') setFilter('followupOnly', target.dataset.tab === 'followup');
  else if (action === 'remove-filter') setFilter(target.dataset.filter, 'all');
  else if (action === 'clear' || action === 'clear-all') resetFilters(action === 'clear-all');
  else if (action === 'close-filters') $('.filter-dropdown').open = false;
  else if (action === 'sort-risk') { state.filters.sort = state.filters.sort === 'risk-desc' ? 'risk-asc' : 'risk-desc'; $('#sort').value = state.filters.sort; state.page = 1; updateResults(); }
  else if (action === 'page') { state.page = Number(target.dataset.page); updateResults(); }
  else if (action === 'followup') {
    const patient = patients.find(p => p.id === target.dataset.id); patient.followup = !patient.followup;
    const persisted = saveStorage('cardia.followups', Object.fromEntries(patients.map(p => [p.id, p.followup])));
    if (p) renderPatient(p); else updateResults();
    toast((patient.followup ? 'Paciente añadido a seguimiento' : 'Paciente retirado del seguimiento') + (!persisted ? ' · solo durante esta sesión' : ''));
  } else if (action === 'event') openEvent(target.dataset.event);
  else if (action === 'chart') { state.chart = target.dataset.chart; $('.chart-tabs').innerHTML = chartTabs(state); $('#chart-content').innerHTML = chart(p, state); }
  else if (action === 'expand-chart') showExpandedChart();
  else if (action === 'close-modal') $('#modal').close();
  else if (action === 'export') exportList();
  else if (action === 'edit-note') {
    const note = notesFor(p).find(n => n.id === target.dataset.note); state.noteEditing = note.id; state.drafts[p.id] = note.text; renderPatient(p); $('#note-text').focus();
  } else if (action === 'cancel-note') { state.noteEditing = null; state.drafts[p.id] = ''; renderPatient(p); }
  else if (action === 'risk-info') openModal('Cómo leer el riesgo en esta demo', '<div class="info-body"><p>El porcentaje representa una <strong>probabilidad ficticia de un evento cardiovascular a 10 años</strong>. No se calcula a partir de las analíticas: está predefinido para probar la interfaz.</p><div class="risk-explanation"><span class="risk-badge low"><i class="dot"></i>Bajo</span><span>Menos del 10 %</span><span class="risk-badge medium"><i class="dot"></i>Medio</span><span>Desde el 10 % hasta menos del 20 %</span><span class="risk-badge high"><i class="dot"></i>Alto</span><span>20 % o más</span></div><p>Estos umbrales son ilustrativos. Las barras de variables también son simuladas y no son una explicación validada de un modelo.</p><div class="modal-note">' + icon('info') + ' Prototipo para presentación. No utilizar para tomar decisiones clínicas.</div></div>');
  else if (action === 'about') openModal('Más foco en el paciente', '<div class="info-body"><p><strong>Cardia</strong> es una primera propuesta para conectar antecedentes, analíticas y evolución en una consulta de Atención Primaria.</p><p>Explora 24 perfiles ficticios, prioriza por riesgo, consulta pruebas y registra notas. Todo funciona en tu navegador, sin cuentas ni servicios externos.</p><div class="about-feature">' + icon('flask') + '<div><strong>Una demo para aprender</strong><p>No hay un modelo de machine learning conectado. Las probabilidades, contribuciones y resultados son datos sintéticos.</p></div></div><p>Las notas y el seguimiento se guardan localmente en este navegador. Para volver al estado inicial, puedes restablecer los datos de la demo.</p><button class="button secondary" data-action="reset-demo">' + icon('reset') + ' Restablecer datos de la demo</button></div>');
  else if (action === 'notifications') openModal('Avisos del cupo', '<div class="notification-item"><span class="stat-icon high">' + icon('heart') + '</span><div><h3>7 pacientes con riesgo alto</h3><p>Puedes encontrarlos en Prioridad clínica y consultar sus fichas.</p></div></div><div class="notification-item"><span class="stat-icon all">' + icon('flask') + '</span><div><h3>Datos listos para explorar</h3><p>24 perfiles de demostración con analíticas e historial.</p></div></div><div class="modal-note">' + icon('info') + ' Avisos de ejemplo, sin sincronización clínica.</div>');
  else if (action === 'profile') openModal('Tu espacio de trabajo', '<div class="profile-dialog"><span class="doctor-avatar">CV</span><h3>Dra. Carmen Vidal</h3><p>Medicina de familia · CAP Sant Martí</p><span class="demo-pill">Perfil de demostración</span></div><div class="modal-note">' + icon('shield') + ' Sesión local de ejemplo. No requiere inicio de sesión.</div>');
  else if (action === 'reset-demo') openModal('Restablecer la demo', '<div class="info-body"><p>Se eliminarán las notas que hayas añadido y los cambios de seguimiento guardados en este navegador. Los perfiles ficticios originales se conservarán.</p><div class="modal-footer"><button class="button secondary" data-action="close-modal">Cancelar</button><button class="button primary" data-action="confirm-reset">Restablecer demo</button></div></div>');
  else if (action === 'confirm-reset') {
    try { localStorage.removeItem('cardia.notes'); localStorage.removeItem('cardia.followups'); location.reload(); } catch { toast('No se ha podido acceder al almacenamiento del navegador'); }
  }
}
$('#app').addEventListener('click', handleAction);
$('#modal').addEventListener('click', event => { if (event.target === $('#modal')) $('#modal').close(); else handleAction(event); });
document.addEventListener('click', event => { const details = $('.filter-dropdown'); if (details && !details.contains(event.target)) details.open = false; });
$('#app').addEventListener('input', event => {
  if (event.target.id === 'patient-search') setFilter('search', event.target.value);
  if (event.target.id === 'note-text') {
    state.drafts[currentPatient().id] = event.target.value;
    $('#note-counter').textContent = event.target.value.length + '/2000';
  }
});
$('#app').addEventListener('change', event => {
  const el = event.target, p = currentPatient();
  if (el.matches('select[data-filter]')) setFilter(el.dataset.filter, el.value);
  if (el.id === 'sort') setFilter('sort', el.value);
  if (el.id === 'top-k') { state.topK = Number(el.value); renderPatient(p); $('#top-k').focus(); }
  if (el.id === 'chart-period') { state.period = el.value; $('#chart-content').innerHTML = chart(p, state); }
});
$('#app').addEventListener('submit', event => {
  if (event.target.id !== 'note-form') return;
  event.preventDefault();
  const p = currentPatient(), text = $('#note-text').value.trim();
  if (!text) { $('#note-text').setCustomValidity('Escribe una observación antes de guardar.'); $('#note-text').reportValidity(); $('#note-text').setCustomValidity(''); return; }
  const list = Array.isArray(savedNotes[p.id]) ? savedNotes[p.id] : [];
  if (state.noteEditing) { const note = list.find(n => n.id === state.noteEditing); if (note) { note.text = text; note.date = new Date().toISOString(); } }
  else list.unshift({ id: crypto.randomUUID(), text, author: 'Dra. Carmen Vidal', date: new Date().toISOString() });
  savedNotes[p.id] = list;
  const persisted = saveStorage('cardia.notes', savedNotes);
  state.drafts[p.id] = ''; state.noteEditing = null; renderPatient(p);
  $('#clinical-notes').scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast(persisted ? 'Nota guardada en este navegador' : 'Nota guardada solo durante esta sesión');
});
window.addEventListener('hashchange', () => { if (!clinicalConfig) return; $('#modal').close(); state.noteEditing = null; state.chart = 'ldl'; shell(); window.scrollTo({ top: 0, behavior: 'instant' }); });
async function boot() {
  try {
    const loaded = await loadClinicalConfig();
    clinicalConfig = loaded.config; ruleConfig = loaded.ruleConfig;
    shell();
    if (!storageAvailable) toast('Almacenamiento local no disponible. Los cambios durarán esta sesión.');
  } catch (error) {
    console.error('Configuración clínica:', error);
    $('#app').innerHTML = '<main class="config-error"><h1>No se puede cargar la configuración</h1><p>Comprueba los archivos de indicadores y reglas y vuelve a intentarlo.</p><button class="button primary" data-action="retry-config">Reintentar</button></main>';
  }
}
boot();

