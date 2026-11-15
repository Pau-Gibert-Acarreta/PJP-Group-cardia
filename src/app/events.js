// Registro de eventos del navegador. Se usa delegación: un único listener por tipo de evento sobre #app.
import { state, clinical } from './state.js';
import { renderApp } from './render.js';
import { handleAction, setFilter, submitNote, submitRiskClassification, setTopK, setChartPeriod, updateDraft } from './actions.js';
import { $ } from '../ui/dom.js';
import { closeModal } from '../ui/components/modal.js';

export function registerEvents() {
  $('#app').addEventListener('click', handleAction);

  // Formularios dentro de la ventana modal.
  $('#modal').addEventListener('submit', event => {
    if (event.target.id !== 'risk-form') return;
    event.preventDefault();
    submitRiskClassification();
  });
  $('#modal').addEventListener('input', event => { if (event.target.id === 'risk-reason') $('#risk-form-error').textContent = ''; });
  $('#modal').addEventListener('change', event => { if (event.target.name === 'risk-level') $('#risk-form-error').textContent = ''; });

  // Clic fuera del contenido del modal (en el fondo): cerrar.
  $('#modal').addEventListener('click', event => { if (event.target === $('#modal')) closeModal(); else handleAction(event); });

  // Clic fuera de un desplegable (filtros o indicador de la gráfica): cerrarlo.
  document.addEventListener('click', event => {
    document.querySelectorAll('.filter-dropdown, .chart-picker').forEach(details => { if (!details.contains(event.target)) details.open = false; });
  });

  // Escape cierra el desplegable del indicador y devuelve el foco a su botón.
  document.addEventListener('keydown', event => {
    const picker = $('.chart-picker[open]');
    if (event.key === 'Escape' && picker) { picker.open = false; picker.querySelector('summary').focus(); }
  });

  $('#app').addEventListener('input', event => {
    if (event.target.id === 'patient-search') setFilter('search', event.target.value);
    if (event.target.id === 'note-text') updateDraft(event.target.value);
  });

  $('#app').addEventListener('change', event => {
    const el = event.target;
    if (el.matches('select[data-filter]')) setFilter(el.dataset.filter, el.value);
    if (el.id === 'sort') setFilter('sort', el.value);
    if (el.id === 'top-k') setTopK(el.value);
    if (el.id === 'chart-period') setChartPeriod(el.value);
  });

  $('#app').addEventListener('submit', event => {
    if (event.target.id !== 'note-form') return;
    event.preventDefault();
    submitNote();
  });

  // Cambio de ruta (#paciente/<id> o listado).
  window.addEventListener('hashchange', () => {
    if (!clinical.config) return;
    closeModal(); state.noteEditing = null; state.chart = 'ldl'; state.knnIncludeLatest = false; renderApp(); window.scrollTo({ top: 0, behavior: 'instant' });
  });
}
