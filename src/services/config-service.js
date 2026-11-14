// Carga y valida la configuración clínica (src/config/*.json).
import { validateClinicalConfig } from '../domain/clinical-config.js';

export async function loadClinicalConfig(fetchFile = fetch) {
  const files = ['indicators.json', 'finding-rules.json'];
  const [config, ruleConfig] = await Promise.all(files.map(async file => {
    const response = await fetchFile(new URL('../config/' + file, import.meta.url));
    if (!response.ok) throw new Error('No se ha podido cargar ' + file);
    return response.json();
  }));
  validateClinicalConfig(config, ruleConfig);
  return { config, ruleConfig };
}
