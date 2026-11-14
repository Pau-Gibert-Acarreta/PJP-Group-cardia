// Pinta la estructura común y la vista que corresponde a la URL actual.
import { $ } from '../ui/dom.js';
import { layout } from '../ui/views/layout.js';
import { renderList } from '../ui/views/patient-list.js';
import { renderPatient } from '../ui/views/patient-detail.js';
import { renderNotFound, renderPatientLoading, renderPatientError } from '../ui/views/status-pages.js';
import { loadPatientDetail } from '../services/patient-service.js';
import { currentPatient, currentPatientId, isPatientRoute } from './router.js';

export function renderApp() {
  const p = currentPatient();
  $('#app').innerHTML = layout(Boolean(p));
  if (!p) { if (isPatientRoute()) renderNotFound(); else renderList(); return; }
  if (p.detailLoaded) { renderPatient(p); return; }
  // La ficha (contacto, eventos, notas) se pide al abrir el paciente.
  renderPatientLoading(p);
  loadPatientDetail(p.id).then(
    () => { if (currentPatientId() === p.id) renderPatient(p); },
    error => { if (currentPatientId() === p.id) renderPatientError(p, error.message); }
  );
}
