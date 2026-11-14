// Convierte los pacientes del backend al objeto que usan las vistas (docs/data-contract.md).
// Función pura: sin red ni almacenamiento, para poder probarla en Node.
import { simulateRisk, stableRandom } from '../data/demo/simulated-risk.js';

const COLORS = ['sage', 'sand', 'rose', 'blue'];

// La API puede devolver un día ("2025-09-03") o un instante ISO; las vistas formatean días.
const day = value => (typeof value === 'string' ? value.slice(0, 10) : '');

export function toPatient(item) {
  const patient = {
    id: item.id,
    cip: item.cip ?? '',
    firstName: item.firstName ?? '',
    lastName: item.lastName ?? '',
    name: item.name,
    initials: item.initials,
    age: item.age,
    sex: item.sex,
    conditions: Array.isArray(item.conditions) ? item.conditions : [],
    followup: Boolean(item.followup),
    lastTest: day(item.lastTest),
    measurements: item.measurements ?? {},
    color: COLORS[Math.floor(stableRandom('color:' + item.id) * COLORS.length)],
    // Solo llegan con la ficha (api.getPatient): ver mergeDetail().
    phone: '', email: '', events: [], notes: [], detailLoaded: false
  };
  return Object.assign(patient, simulateRisk(patient));
}

// Añade los datos de la ficha al paciente del listado, conservando el riesgo simulado.
export function mergeDetail(patient, detail) {
  Object.assign(patient, {
    phone: detail.phone ?? '',
    email: detail.email ?? '',
    conditions: Array.isArray(detail.conditions) ? detail.conditions : patient.conditions,
    followup: Boolean(detail.followup),
    lastTest: day(detail.lastTest) || patient.lastTest,
    measurements: detail.measurements ?? patient.measurements,
    // La línea temporal se pinta de la más antigua a la más reciente.
    events: (detail.events ?? [])
      .map(e => ({ ...e, time: e.date, date: day(e.date) }))
      .sort((a, b) => a.time.localeCompare(b.time)),
    notes: detail.notes ?? [],
    detailLoaded: true
  });
  return patient;
}
