// Pantallas de estado: carga, paciente no encontrado y errores de configuración o del servidor.
import { $ } from '../dom.js';
import { esc } from '../../utils/text.js';

export function renderLoading() {
  $('#app').innerHTML = '<main class="config-error" aria-busy="true"><h1>Cargando pacientes…</h1><p>Recuperando el cupo desde el servidor.</p></main>';
}

export function renderNotFound() {
  $('#main-content').innerHTML = '<div class="card empty-state"><h1>Paciente no encontrado</h1><p>El identificador no corresponde a ningún paciente del cupo.</p><a class="button primary" href="#">Volver a pacientes</a></div>';
}

export function renderPatientLoading(p) {
  $('#main-content').innerHTML = '<div class="card empty-state" aria-busy="true"><h1>Cargando la ficha de ' + esc(p.name) + '…</h1><p>Recuperando contacto, historia y notas.</p></div>';
}

export function renderPatientError(p, message) {
  $('#main-content').innerHTML = '<div class="card empty-state"><h1>No se puede cargar la ficha de ' + esc(p.name) + '</h1><p>' + esc(message) + '</p>' +
    '<a class="button primary" href="#">Volver a pacientes</a></div>';
}

export function renderConfigError() {
  $('#app').innerHTML = '<main class="config-error"><h1>No se puede cargar la configuración</h1><p>Comprueba los archivos de indicadores y reglas y vuelve a intentarlo.</p><button class="button primary" data-action="retry-config">Reintentar</button></main>';
}

export function renderApiError(message) {
  $('#app').innerHTML = '<main class="config-error"><h1>No se pueden cargar los pacientes</h1><p>' + esc(message) + '</p>' +
    '<p>Comprueba que el backend está en marcha (<code>uv run uvicorn app.main:app</code> en <code>backend/</code>) y vuelve a intentarlo.</p>' +
    '<button class="button primary" data-action="retry-config">Reintentar</button></main>';
}
