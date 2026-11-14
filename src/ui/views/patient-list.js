// Vista del listado de pacientes: resumen del cupo, pestañas, búsqueda, filtros, tabla y paginación.
import { state, clinical } from '../../app/state.js';
import { getPatients } from '../../services/patient-service.js';
import { selectPatients } from '../../domain/patient-filters.js';
import { effectiveRiskLevel, RISK_LABELS } from '../../domain/risk.js';
import { esc } from '../../utils/text.js';
import { $ } from '../dom.js';
import { icon } from '../icons.js';
import { overviewHeader, overviewRow } from '../components/overview-table.js';

const HEADINGS = {
  priority: ['Prioridad clínica', 'Una mirada a los pacientes con mayor riesgo cardiovascular.'],
  followup: ['Pacientes en seguimiento', 'Tu selección de pacientes para seguir su evolución de cerca.'],
  patients: ['Tus pacientes, de un vistazo', 'Detecta señales, conecta la información y prioriza la atención.']
};

const CONDITIONS = ['Hipertensión', 'Diabetes tipo 2', 'Enf. renal crónica', 'Dislipidemia', 'Tabaquismo'];

// Contadores con separador de miles (4.434).
const count = n => new Intl.NumberFormat('es-ES').format(n);

const SORT_OPTIONS = [['risk-desc', 'Mayor riesgo primero'], ['risk-asc', 'Menor riesgo primero'], ['name', 'Nombre: A–Z'], ['age', 'Mayor edad primero'], ['recent', 'Analítica más reciente']];

function statCard(level, label, count, caption, glyph) {
  return '<button class="stat-card ' + level + '" data-action="risk-filter" data-risk="' + level + '">' +
    '<div class="stat-title">' + label + '<span class="stat-icon">' + icon(glyph) + '</span></div>' +
    '<div class="stat-value">' + count + '<span>pacientes</span></div>' +
    '<div class="stat-caption">' + (level !== 'all' ? '<span class="dot"></span>' : '') + caption + '</div></button>';
}

function filterSelect(key, label, options) {
  return '<label class="form-label">' + label + '<select data-filter="' + key + '">' +
    options.map(([v, t]) => '<option value="' + v + '" ' + (state.filters[key] === v ? 'selected' : '') + '>' + t + '</option>').join('') + '</select></label>';
}

function pageHeading() {
  const [title, subtitle] = HEADINGS[state.nav] || HEADINGS.patients;
  return '<section class="page-heading"><div><div class="eyebrow">VISIÓN GLOBAL</div><h1>' + title + '</h1><p>' + subtitle + '</p></div>' +
    '<div class="date-label">' + icon('calendar') + ' 14 de noviembre de 2026</div></section>';
}

function summaryCards(patients) {
  const byLevel = level => count(patients.filter(p => effectiveRiskLevel(p) === level).length);
  return '<section class="stats-grid" aria-label="Resumen del cupo">' +
    statCard('all', 'Total de pacientes', count(patients.length), 'En tu cupo', 'users') +
    statCard('high', 'Riesgo alto', byLevel('high'), 'Prioriza su revisión', 'heart') +
    statCard('medium', 'Riesgo medio', byLevel('medium'), 'Observa su evolución', 'activity') +
    statCard('low', 'Riesgo bajo', byLevel('low'), 'Seguimiento habitual', 'shield') + '</section>';
}

function filtersDropdown() {
  return '<details class="filter-dropdown"><summary class="button secondary">' + icon('filter') + ' Filtros <span id="filter-number"></span></summary>' +
    '<div class="filter-popover"><div class="popover-heading"><strong>Filtrar pacientes</strong><button class="text-button" data-action="clear">Restablecer</button></div>' +
    filterSelect('risk', 'Riesgo cardiovascular', [['all', 'Todos los niveles'], ['high', 'Alto · ≥ 20 %'], ['medium', 'Medio · 10 a < 20 %'], ['low', 'Bajo · < 10 %']]) +
    filterSelect('sex', 'Sexo', [['all', 'Todos'], ['Mujer', 'Mujer'], ['Hombre', 'Hombre']]) +
    filterSelect('age', 'Edad', [['all', 'Todas las edades'], ['under65', 'Menores de 65 años'], ['65plus', '65 años o más']]) +
    filterSelect('condition', 'Antecedentes', [['all', 'Todos los antecedentes'], ...CONDITIONS.map(x => [x, x])]) +
    '<small>Umbrales ilustrativos, solo para esta demo.</small><button class="button primary full-width" data-action="close-filters">Ver resultados</button></div></details>';
}

function patientPanel(patients) {
  return '<section class="patient-panel">' +
    '<div class="panel-heading"><div><h2>Listado de pacientes <span class="count-pill" id="result-count">' + count(patients.length) + '</span></h2><p>La información que necesitas para saber por dónde empezar.</p></div>' +
    '<button class="button secondary export-button" data-action="export">' + icon('download') + ' Exportar listado</button></div>' +
    '<div class="list-tabs">' +
    '<button data-action="tab" data-tab="all" class="' + (!state.filters.followupOnly ? 'selected' : '') + '">Todos los pacientes <span>' + count(patients.length) + '</span></button>' +
    '<button data-action="tab" data-tab="followup" class="' + (state.filters.followupOnly ? 'selected' : '') + '">En seguimiento <span id="followup-count">' + patients.filter(p => p.followup).length + '</span></button></div>' +
    '<div class="toolbar"><label class="search-field">' + icon('search') + '<input id="patient-search" type="search" placeholder="Buscar por nombre o identificador…" aria-label="Buscar pacientes" value="' + esc(state.filters.search) + '"></label>' +
    filtersDropdown() +
    '<label class="sort-select">' + icon('sort') + '<select id="sort" aria-label="Ordenar pacientes">' +
    SORT_OPTIONS.map(([v, t]) => '<option value="' + v + '" ' + (state.filters.sort === v ? 'selected' : '') + '>' + t + '</option>').join('') + '</select></label></div>' +
    '<div id="active-filters" class="active-filters"></div><div id="patient-results"></div></section>';
}

const riskLegend = () =>
  '<div class="legend"><span class="legend-label">Semáforo de riesgo</span><span><i class="dot low"></i> Bajo &lt; 10 %</span><span><i class="dot medium"></i> Medio 10–&lt;20 %</span><span><i class="dot high"></i> Alto ≥ 20 %</span>' +
  '<button data-action="risk-info">' + icon('info') + ' ¿Cómo se interpreta?</button></div>';

export function renderList() {
  const patients = getPatients();
  $('#main-content').innerHTML = pageHeading() + summaryCards(patients) + patientPanel(patients) + riskLegend();
  updateResults();
}

// Páginas visibles: la primera, la última y dos a cada lado de la actual, con "…" entre huecos.
export function pageWindow(current, pages) {
  const wanted = new Set([1, pages, current - 2, current - 1, current, current + 1, current + 2]);
  const list = [...wanted].filter(n => n >= 1 && n <= pages).sort((a, b) => a - b);
  return list.flatMap((n, i) => (i && n - list[i - 1] > 1 ? ['gap', n] : [n]));
}

function pagination(items, start) {
  const pages = Math.ceil(items.length / state.perPage);
  const pageButton = n => n === 'gap'
    ? '<span class="page-gap" aria-hidden="true">…</span>'
    : '<button class="page-number ' + (state.page === n ? 'current' : '') + '" data-action="page" data-page="' + n + '" aria-label="Página ' + n + '" ' + (state.page === n ? 'aria-current="page"' : '') + '>' + n + '</button>';
  return '<div class="pagination"><span>Mostrando <strong>' + count(start + 1) + '–' + count(Math.min(start + state.perPage, items.length)) + '</strong> de <strong>' + count(items.length) + '</strong> pacientes</span><div>' +
    '<button class="icon-button" aria-label="Página anterior" data-action="page" data-page="' + (state.page - 1) + '" ' + (state.page === 1 ? 'disabled' : '') + '>' + icon('arrow') + '</button>' +
    pageWindow(state.page, pages).map(pageButton).join('') +
    '<button class="icon-button" aria-label="Página siguiente" data-action="page" data-page="' + (state.page + 1) + '" ' + (start + state.perPage >= items.length ? 'disabled' : '') + '>' + icon('chevron') + '</button></div></div>';
}

const emptyResults = () =>
  '<div class="empty-state"><span>' + icon('search') + '</span><h3>No hay pacientes con estos criterios</h3><p>Prueba con otro nombre o ajusta los filtros de búsqueda.</p>' +
  '<button class="button secondary" data-action="clear-all">Restablecer búsqueda y filtros</button></div>';

// Recalcula resultados, contadores, filtros activos y tabla sin volver a pintar toda la vista.
export function updateResults() {
  const patients = getPatients();
  const items = selectPatients(patients, state.filters);
  state.page = Math.max(1, Math.min(state.page, Math.ceil(items.length / state.perPage)));
  const start = (state.page - 1) * state.perPage;
  $('#result-count').textContent = count(items.length); $('#followup-count').textContent = count(patients.filter(p => p.followup).length);
  document.querySelectorAll('.stat-card').forEach(el => { const selected = el.dataset.risk === state.filters.risk; el.classList.toggle('stat-selected', selected); el.setAttribute('aria-pressed', selected); });
  document.querySelectorAll('.list-tabs button').forEach(el => el.classList.toggle('selected', (el.dataset.tab === 'followup') === state.filters.followupOnly));
  const filters = ['risk', 'sex', 'age', 'condition'].filter(k => state.filters[k] !== 'all');
  $('#filter-number').textContent = filters.length ? filters.length : '';
  const labels = { risk: 'Riesgo ' + (RISK_LABELS[state.filters.risk] || ''), sex: state.filters.sex, age: state.filters.age === '65plus' ? '≥ 65 años' : '< 65 años', condition: state.filters.condition };
  $('#active-filters').innerHTML = filters.map(k => '<button class="filter-chip" data-action="remove-filter" data-filter="' + k + '">' + esc(labels[k]) + icon('close') + '</button>').join('') +
    (filters.length ? '<button class="text-button" data-action="clear">Limpiar filtros</button>' : '');
  document.querySelectorAll('select[data-filter]').forEach(el => el.value = state.filters[el.dataset.filter]);
  $('#patient-results').innerHTML = items.length
    ? '<div class="table-scroll" role="region" aria-label="Listado con indicadores clínicos, desplazable horizontalmente" tabindex="0"><table class="patient-table overview-table">' +
      overviewHeader(clinical.config, state.filters.sort) + '<tbody>' +
      items.slice(start, start + state.perPage).map(p => overviewRow(p, clinical.config)).join('') +
      '</tbody></table></div>' + pagination(items, start)
    : emptyResults();
}
