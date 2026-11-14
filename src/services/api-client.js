// Cliente HTTP del Core Backend API (backend/, documentado en backend/README.md).
// scripts/serve.mjs reenvía /api/* al backend, así que basta con rutas relativas.

export const API_BASE_URL = '/api/v1';

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function request(path, { method = 'GET', body } = {}) {
  let response;
  try {
    response = await fetch(API_BASE_URL + path, {
      method,
      headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined
    });
  } catch {
    throw new ApiError(0, 'No se puede conectar con el servidor');
  }
  if (!response.ok) {
    const detail = await response.json().then(data => data?.detail, () => null);
    throw new ApiError(response.status, typeof detail === 'string' ? detail : 'Error ' + response.status + ' en ' + method + ' ' + path);
  }
  return response.status === 204 ? null : response.json();
}

const patient = id => '/patients/' + encodeURIComponent(id);

export const api = {
  // Cupo completo con sus mediciones: el listado filtra, ordena y cuenta en el navegador.
  getPatients: () => request('/patients?limit=5000&include_measurements=true'),
  // Ficha completa: contacto, mediciones, eventos y notas.
  getPatient: id => request(patient(id)),
  getMeasurements: id => request(patient(id) + '/measurements'),
  setFollowup: (id, followup) => request(patient(id) + '/followup', { method: 'PUT', body: { followup } }),
  getNotes: id => request(patient(id) + '/notes'),
  createNote: (id, text) => request(patient(id) + '/notes', { method: 'POST', body: { text } }),
  updateNote: (id, noteId, text) => request(patient(id) + '/notes/' + encodeURIComponent(noteId), { method: 'PUT', body: { text } }),
  // Aún sin usar: el riesgo de ML y su ajuste clínico siguen simulados en el frontend.
  getRiskAssessments: id => request(patient(id) + '/risk-assessments'),
  setRiskClassification: (id, level, reason) => request(patient(id) + '/risk-classification', { method: 'PUT', body: { level, reason } }),
  clearRiskClassification: id => request(patient(id) + '/risk-classification', { method: 'DELETE' })
};
