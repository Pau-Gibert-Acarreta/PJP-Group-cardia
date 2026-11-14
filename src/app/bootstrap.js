// Arranque: carga la configuración clínica y pinta la aplicación.
import { clinical } from './state.js';
import { renderApp } from './render.js';
import { loadClinicalConfig } from '../services/config-service.js';
import { isStorageAvailable } from '../services/storage.js';
import '../services/risk-service.js'; // aplica los ajustes de clasificación guardados
import { toast } from '../ui/components/toast.js';
import { renderConfigError } from '../ui/views/status-pages.js';

export async function boot() {
  try {
    const loaded = await loadClinicalConfig();
    clinical.config = loaded.config; clinical.ruleConfig = loaded.ruleConfig;
    renderApp();
    if (!isStorageAvailable()) toast('Almacenamiento local no disponible. Los cambios durarán esta sesión.');
  } catch (error) {
    console.error('Configuración clínica:', error);
    renderConfigError();
  }
}
