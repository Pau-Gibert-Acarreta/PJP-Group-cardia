// Cliente HTTP para el futuro backend de Cardia.
//
// ⚠ TODAVÍA NO SE USA: la aplicación funciona con los datos de demostración.
// Es el punto de partida para conectar el backend: cuando exista, patient-service.js y
// notes-service.js llamarán a estas funciones en lugar de usar los datos de data/demo/.
// Los nombres de los endpoints son una propuesta; ajústalos al contrato real del backend.

export const API_BASE_URL = '/api/v1';

async function request(path, { method = 'GET', body } = {}) {
  const response = await fetch(API_BASE_URL + path, {
    method,
    headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    credentials: 'include',
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) throw new Error('Error ' + response.status + ' en ' + method + ' ' + path);
  return response.status === 204 ? null : response.json();
}

export const api = {
  // Pacientes del cupo, con el último riesgo calculado y datos de cabecera.
  getPatients: () => request('/patients'),
  getPatient: id => request('/patients/' + encodeURIComponent(id)),
  // Mediciones normalizadas: { [field]: [{ value, date, unit }] } (ver docs/data-contract.md).
  getMeasurements: id => request('/patients/' + encodeURIComponent(id) + '/measurements'),
  // Resultados de los modelos (SCORE2, SCORE2-OP, KFRE, modelo propio) con fecha y versión.
  getRiskAssessments: id => request('/patients/' + encodeURIComponent(id) + '/risk-assessments'),
  // Clasificación de riesgo ajustada por el médico (la probabilidad del modelo no se modifica).
  setRiskClassification: (id, level, reason) => request('/patients/' + encodeURIComponent(id) + '/risk-classification', { method: 'PUT', body: { level, reason } }),
  clearRiskClassification: id => request('/patients/' + encodeURIComponent(id) + '/risk-classification', { method: 'DELETE' }),
  setFollowup: (id, followup) => request('/patients/' + encodeURIComponent(id) + '/followup', { method: 'PUT', body: { followup } }),
  getNotes: id => request('/patients/' + encodeURIComponent(id) + '/notes'),
  createNote: (id, text) => request('/patients/' + encodeURIComponent(id) + '/notes', { method: 'POST', body: { text } }),
  updateNote: (id, noteId, text) => request('/patients/' + encodeURIComponent(id) + '/notes/' + encodeURIComponent(noteId), { method: 'PUT', body: { text } })
};
