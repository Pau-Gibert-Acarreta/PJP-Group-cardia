// Convierte los pacientes del backend al objeto que usan las vistas (docs/data-contract.md).
// Función pura: sin red ni almacenamiento, para poder probarla en Node.
// El riesgo es la predicción guardada del Motor de Riesgo (ml/, modelo de Cox): risk en %,
// y en la ficha, factors (SHAP) e history.risk.

// Número en [0, 1) estable para cada texto (FNV-1a): color del avatar.
export function stableRandom(text) {
  let h = 2166136261;
  for (const c of String(text)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967296;
}

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
    // Predicción del modelo (null si el paciente aún no tiene ninguna)
    risk: Number.isFinite(item.risk) ? item.risk : null,
    riskAt: item.riskAt ?? null,
    riskModelVersion: item.riskModelVersion ?? null,
    history: { risk: Number.isFinite(item.risk) ? [item.risk] : [] },
    // Solo llegan con la ficha (api.getPatient): ver mergeDetail().
    phone: '', email: '', events: [], notes: [], factors: [], detailLoaded: false
  };
  return patient;
}

// Añade los datos de la ficha al paciente del listado.
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
    risk: Number.isFinite(detail.risk) ? detail.risk : patient.risk,
    factors: Array.isArray(detail.factors) ? detail.factors : [],
    history: { risk: Array.isArray(detail.history?.risk) && detail.history.risk.length ? detail.history.risk : patient.history.risk },
    detailLoaded: true
  });
  return patient;
}
