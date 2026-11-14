// Rutas basadas en el hash de la URL: "#" = listado, "#paciente/<id>" = ficha del paciente.
import { findPatient } from '../services/patient-service.js';

export const PATIENT_ROUTE = '#paciente/';

export const currentPatientId = () => location.hash.match(/^#paciente\/([^/]+)$/)?.[1];

export const currentPatient = () => findPatient(currentPatientId());

export const isPatientRoute = () => location.hash.startsWith(PATIENT_ROUTE);

export const goToPatient = id => { location.hash = 'paciente/' + id; };
