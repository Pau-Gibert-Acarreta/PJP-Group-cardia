// Acciones de la interfaz. Cada botón o enlace interactivo lleva data-action="<nombre>" y se resuelve aquí.
import { state, clinical, defaultFilters } from './state.js';
import { currentPatient, goToPatient } from './router.js';
import { renderApp } from './render.js';
import { boot } from './bootstrap.js';
import { getPatients, toggleFollowup } from '../services/patient-service.js';
import { notesFor, saveNote } from '../services/notes-service.js';
import { removeStorage, STORAGE_KEYS } from '../services/storage.js';
import { setRiskClassification, clearRiskClassification } from '../services/risk-service.js';
import { riskLevel, RISK_LABELS } from '../domain/risk.js';
import { buildPatientsCsv, downloadCsv } from '../services/export-service.js';
import { $ } from '../ui/dom.js';
import { toast } from '../ui/components/toast.js';
import { closeModal } from '../ui/components/modal.js';
import { chartPicker, chart } from '../ui/components/chart.js';
import { updateResults } from '../ui/views/patient-list.js';
import { renderPatient, mountSimilarCases } from '../ui/views/patient-detail.js';
import { similarCasesBody } from '../ui/components/similar-cases.js';
import { openEvent, openExpandedChart } from '../ui/dialogs/patient-dialogs.js';
import { openRiskClassification } from '../ui/dialogs/risk-classification-dialog.js';
import { openRiskInfo, openAbout, openNotifications, openProfile, openResetConfirm } from '../ui/dialogs/info-dialogs.js';

// ---- Listado: filtros, pestañas y paginación ----

export function setFilter(key, value) { state.filters[key] = value; state.page = 1; updateResults(); }

function resetFilters(all = false) {
  const search = all ? '' : state.filters.search;
  state.filters = { ...defaultFilters(), search }; state.page = 1; state.nav = 'patients'; renderApp();
}

function navigate(nav) {
  state.nav = nav; state.filters = defaultFilters(); state.page = 1;
  if (state.nav === 'priority') state.filters.risk = 'high';
  if (state.nav === 'followup') state.filters.followupOnly = true;
  if (location.hash) location.hash = ''; else renderApp();
}

function toggleRiskSort() {
  state.filters.sort = state.filters.sort === 'risk-desc' ? 'risk-asc' : 'risk-desc';
  $('#sort').value = state.filters.sort; state.page = 1; updateResults();
}

function exportList() {
  downloadCsv(buildPatientsCsv(getPatients(), state.filters, clinical.config), 'cardia-pacientes.csv');
  toast('Listado filtrado exportado');
}

// ---- Ficha del paciente ----

async function followup(id, p) {
  const refresh = () => { if (p) renderPatient(p); else updateResults(); };
  try {
    const patient = await toggleFollowup(id);
    refresh();
    toast(patient.followup ? 'Paciente añadido a seguimiento' : 'Paciente retirado del seguimiento');
  } catch (error) {
    refresh();
    toast('No se ha podido guardar el seguimiento: ' + error.message);
  }
}

function selectChart(p, key) {
  state.chart = key; $('.chart-picker-slot').innerHTML = chartPicker(p, state); $('.chart-picker-trigger').focus(); $('#chart-content').innerHTML = chart(p, state);
}

function editNote(p, noteId) {
  const note = notesFor(p).find(n => n.id === noteId);
  state.noteEditing = note.id; state.drafts[p.id] = note.text; renderPatient(p); $('#note-text').focus();
}

function cancelNote(p) { state.noteEditing = null; state.drafts[p.id] = ''; renderPatient(p); }

export async function submitNote() {
  const p = currentPatient(), text = $('#note-text').value.trim();
  if (!text) { $('#note-text').setCustomValidity('Escribe una observación antes de guardar.'); $('#note-text').reportValidity(); $('#note-text').setCustomValidity(''); return; }
  const button = $('#note-form button[type="submit"]');
  button.disabled = true;
  try {
    await saveNote(p, text, state.noteEditing);
  } catch (error) {
    // Se conserva el borrador para no perder lo escrito.
    button.disabled = false;
    toast('No se ha podido guardar la nota: ' + error.message);
    return;
  }
  state.drafts[p.id] = ''; state.noteEditing = null;
  if (currentPatient() !== p) return;
  renderPatient(p);
  $('#clinical-notes').scrollIntoView({ behavior: 'smooth', block: 'start' });
  toast('Nota guardada');
}

export function setTopK(value) { state.topK = Number(value); renderPatient(currentPatient()); $('#top-k').focus(); }

export function setChartPeriod(value) { state.period = value; $('#chart-content').innerHTML = chart(currentPatient(), state); }

export function updateDraft(value) { state.drafts[currentPatient().id] = value; $('#note-counter').textContent = value.length + '/2000'; }

// ---- Casos similares (KNN) ----

// Cambia entre comparar sin la última prueba (por defecto) y con ella; la segunda se calcula al momento.
function setKnnMode(p, includeLatest) {
  if (state.knnIncludeLatest === includeLatest) return;
  state.knnIncludeLatest = includeLatest;
  document.querySelectorAll('[data-action="knn-mode"]').forEach(el => {
    const selected = (el.dataset.latest === 'true') === includeLatest;
    el.classList.toggle('selected', selected); el.setAttribute('aria-pressed', selected);
  });
  $('#similar-cases-body').innerHTML = similarCasesBody({ loading: true });
  mountSimilarCases(p);
}

// ---- Ajuste clínico de la clasificación de riesgo ----

export function submitRiskClassification() {
  const p = currentPatient();
  const level = $('#risk-form input[name="risk-level"]:checked')?.value;
  const reason = $('#risk-reason').value.trim();
  const error = message => { $('#risk-form-error').textContent = message; };
  if (!level) return error('Elige una clasificación.');
  if (level !== riskLevel(p.risk) && !reason) { error('Indica el motivo del ajuste.'); $('#risk-reason').focus(); return; }
  const persisted = setRiskClassification(p.id, level, reason);
  closeModal(); renderApp();
  const message = level === riskLevel(p.risk) ? 'Se mantiene la clasificación del modelo: ' + RISK_LABELS[level] : 'Clasificación ajustada a riesgo ' + RISK_LABELS[level].toLowerCase();
  toast(message + (!persisted ? ' · solo durante esta sesión' : ''));
}

function restoreRiskClassification(p) {
  const persisted = clearRiskClassification(p.id);
  closeModal(); renderApp();
  toast('Clasificación restablecida a la del modelo' + (!persisted ? ' · solo durante esta sesión' : ''));
}

function confirmReset() {
  // Notas y seguimiento están en el servidor; aquí solo se borra lo local (ajustes de la clasificación
  // y las claves antiguas de notas y seguimiento de la versión sin backend).
  try { removeStorage(STORAGE_KEYS.notes, STORAGE_KEYS.followups, STORAGE_KEYS.riskOverrides); location.reload(); } catch { toast('No se ha podido acceder al almacenamiento del navegador'); }
}

// ---- Despachador de clics ----

export function handleAction(event) {
  const target = event.target.closest('[data-action]');
  if (!target) {
    // Clic en cualquier parte de una fila del listado: abre la ficha.
    const row = event.target.closest('[data-patient-row]');
    if (row && !event.target.closest('a,button,input,select')) goToPatient(row.dataset.patientRow);
    return;
  }
  const action = target.dataset.action, p = currentPatient();
  switch (action) {
    case 'retry-config': boot(); break;
    case 'nav': navigate(target.dataset.nav); break;
    case 'risk-filter': setFilter('risk', state.filters.risk === target.dataset.risk && target.dataset.risk !== 'all' ? 'all' : target.dataset.risk); break;
    case 'tab': setFilter('followupOnly', target.dataset.tab === 'followup'); break;
    case 'remove-filter': setFilter(target.dataset.filter, 'all'); break;
    case 'clear': case 'clear-all': resetFilters(action === 'clear-all'); break;
    case 'close-filters': $('.filter-dropdown').open = false; break;
    case 'sort-risk': toggleRiskSort(); break;
    case 'page': state.page = Number(target.dataset.page); updateResults(); break;
    case 'followup': followup(target.dataset.id, p); break;
    case 'event': openEvent(p, target.dataset.event); break;
    case 'chart': selectChart(p, target.dataset.chart); break;
    case 'knn-mode': setKnnMode(p, target.dataset.latest === 'true'); break;
    case 'expand-chart': openExpandedChart(p); break;
    case 'close-modal': closeModal(); break;
    case 'export': exportList(); break;
    case 'edit-note': editNote(p, target.dataset.note); break;
    case 'cancel-note': cancelNote(p); break;
    case 'edit-risk': openRiskClassification(p); break;
    case 'restore-risk': restoreRiskClassification(p); break;
    case 'risk-info': openRiskInfo(); break;
    case 'about': openAbout(); break;
    case 'notifications': openNotifications(); break;
    case 'profile': openProfile(); break;
    case 'reset-demo': openResetConfirm(); break;
    case 'confirm-reset': confirmReset(); break;
  }
}
