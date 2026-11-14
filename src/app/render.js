// Pinta la estructura común y la vista que corresponde a la URL actual.
import { $ } from '../ui/dom.js';
import { layout } from '../ui/views/layout.js';
import { renderList } from '../ui/views/patient-list.js';
import { renderPatient } from '../ui/views/patient-detail.js';
import { renderNotFound } from '../ui/views/status-pages.js';
import { currentPatient, isPatientRoute } from './router.js';

export function renderApp() {
  const p = currentPatient();
  $('#app').innerHTML = layout(Boolean(p));
  if (p) renderPatient(p); else if (isPatientRoute()) renderNotFound(); else renderList();
}
