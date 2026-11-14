// Pantallas de estado: paciente no encontrado y error al cargar la configuración.
import { $ } from '../dom.js';

export function renderNotFound() {
  $('#main-content').innerHTML = '<div class="card empty-state"><h1>Paciente no encontrado</h1><p>El identificador no corresponde a un paciente de esta demo.</p><a class="button primary" href="#">Volver a pacientes</a></div>';
}

export function renderConfigError() {
  $('#app').innerHTML = '<main class="config-error"><h1>No se puede cargar la configuración</h1><p>Comprueba los archivos de indicadores y reglas y vuelve a intentarlo.</p><button class="button primary" data-action="retry-config">Reintentar</button></main>';
}
