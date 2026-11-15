// Pacientes similares (KNN, k = 7) calculados por el backend.
// Sin la última prueba: se pide al abrir la ficha. Con la última prueba: a petición del médico.
import { api } from './api-client.js';

const cache = new Map();

const key = (id, includeLatest) => id + ':' + (includeLatest ? 'with' : 'without');

export const cachedSimilar = (id, includeLatest) => cache.get(key(id, includeLatest));

// Devuelve { data } o { error, status }. Las respuestas se guardan para no repetir la consulta.
export async function loadSimilar(id, includeLatest) {
  const k = key(id, includeLatest);
  if (!cache.has(k)) {
    cache.set(k, api.getSimilar(id, includeLatest).then(
      data => ({ data }),
      error => { cache.delete(k); return { error: error.message, status: error.status }; }
    ));
  }
  return cache.get(k);
}

// Al guardar pruebas nuevas, los casos similares del paciente cambian.
export function forgetSimilar(id) {
  cache.delete(key(id, false)); cache.delete(key(id, true));
}
