// Arranque: carga la configuración clínica y los pacientes del backend, y pinta la aplicación.
import { clinical } from './state.js';
import { renderApp } from './render.js';
import { loadClinicalConfig } from '../services/config-service.js';
import { loadPatients } from '../services/patient-service.js';
import { applyStoredRiskOverrides } from '../services/risk-service.js';
import { isStorageAvailable } from '../services/storage.js';
import { toast } from '../ui/components/toast.js';
import { renderConfigError, renderApiError, renderLoading } from '../ui/views/status-pages.js';

export async function boot() {
  renderLoading();
  let loaded;
  try {
    loaded = await loadClinicalConfig();
  } catch (error) {
    console.error('Configuración clínica:', error);
    renderConfigError();
    return;
  }
  try {
    applyStoredRiskOverrides(await loadPatients());
  } catch (error) {
    console.error('Pacientes:', error);
    renderApiError(error.message);
    return;
  }
  clinical.config = loaded.config; clinical.ruleConfig = loaded.ruleConfig;
  renderApp();
  if (!isStorageAvailable()) toast('Almacenamiento local no disponible. Los ajustes de riesgo durarán esta sesión.');
}
