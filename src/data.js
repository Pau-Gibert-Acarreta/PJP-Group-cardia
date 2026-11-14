import { makeDemoMeasurements } from './demo-measurements.js';
// Registros ficticios para la demo. No representan un modelo clínico.
export const DEMO_DATE = '2026-11-14';
export const RISK_LABELS = { high: 'Alto', medium: 'Medio', low: 'Bajo' };
export function riskLevel(risk) { return risk >= 20 ? 'high' : risk >= 10 ? 'medium' : 'low'; }
export const formatNumber = (value, digits = 0) => new Intl.NumberFormat('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
export const formatDate = (date, long = false) => new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: long ? 'long' : 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(date + 'T12:00:00Z'));
export const normalize = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
const records = [
  ['María', 'García López', 67, 'Mujer', 32.4, ['Hipertensión', 'Diabetes tipo 2'], true, '2026-11-10'],
  ['Antonio', 'Martínez Ruiz', 72, 'Hombre', 28.7, ['Hipertensión', 'Enf. renal crónica'], true, '2026-11-09'],
  ['Carmen', 'Sánchez Pérez', 61, 'Mujer', 24.1, ['Diabetes tipo 2', 'Dislipidemia'], false, '2026-11-11'],
  ['José', 'Rodríguez Martín', 58, 'Hombre', 22.8, ['Hipertensión', 'Tabaquismo'], true, '2026-11-07'],
  ['Isabel', 'Fernández Díaz', 69, 'Mujer', 21.3, ['Enf. renal crónica'], false, '2026-11-06'],
  ['Manuel', 'López Moreno', 76, 'Hombre', 20.5, ['Hipertensión', 'Diabetes tipo 2'], false, '2026-11-08'],
  ['Francisco', 'Muñoz Romero', 64, 'Hombre', 20.1, ['Dislipidemia', 'Tabaquismo'], true, '2026-11-03'],
  ['Laura', 'Navarro Gil', 54, 'Mujer', 17.6, ['Diabetes tipo 2'], true, '2026-11-12'],
  ['Pedro', 'Jiménez Torres', 63, 'Hombre', 16.2, ['Hipertensión'], false, '2026-11-02'],
  ['Ana', 'Ruiz Serrano', 59, 'Mujer', 14.8, ['Dislipidemia'], true, '2026-10-28'],
  ['Javier', 'Moreno Molina', 56, 'Hombre', 13.5, ['Tabaquismo'], false, '2026-10-30'],
  ['Dolores', 'Romero Alonso', 71, 'Mujer', 12.9, ['Hipertensión'], true, '2026-10-24'],
  ['Miguel', 'Alonso Gutiérrez', 62, 'Hombre', 11.7, ['Diabetes tipo 2'], false, '2026-10-22'],
  ['Pilar', 'Serrano Ramos', 52, 'Mujer', 10.4, ['Dislipidemia'], false, '2026-11-04'],
  ['David', 'Torres Vega', 47, 'Hombre', 8.7, ['Hipertensión'], false, '2026-11-01'],
  ['Elena', 'Vega Castro', 49, 'Mujer', 7.8, ['Dislipidemia'], true, '2026-10-19'],
  ['Rafael', 'Castro Ortega', 55, 'Hombre', 7.1, ['Tabaquismo'], false, '2026-10-17'],
  ['Marta', 'Ortega Rubio', 44, 'Mujer', 6.2, [], false, '2026-11-05'],
  ['Daniel', 'Rubio Marín', 41, 'Hombre', 5.6, [], false, '2026-10-15'],
  ['Lucía', 'Marín Iglesias', 38, 'Mujer', 4.8, [], false, '2026-10-12'],
  ['Alberto', 'Iglesias Santos', 46, 'Hombre', 4.2, ['Dislipidemia'], false, '2026-10-10'],
  ['Paula', 'Santos León', 35, 'Mujer', 3.5, [], false, '2026-10-07'],
  ['Sergio', 'León Méndez', 33, 'Hombre', 2.9, [], false, '2026-10-05'],
  ['Cristina', 'Méndez Costa', 40, 'Mujer', 2.1, [], false, '2026-10-02']
];
export const patients = records.map(([firstName, lastName, age, sex, risk, conditions, followup, lastTest], i) => {
  const high = riskLevel(risk) === 'high';
  const ldl = i === 0 ? 162 : Math.round(84 + risk * 2.1 + (i % 3) * 5);
  const systolic = i === 0 ? 148 : Math.round(112 + risk * 1.1);
  const hba1c = i === 0 ? 7.2 : +(5.2 + (conditions.includes('Diabetes tipo 2') ? 1.8 : (i % 4) * .2)).toFixed(1);
  const egfr = i === 0 ? 68 : conditions.includes('Enf. renal crónica') ? 48 + i : 75 + i % 20;
  const acr = i === 0 ? 42 : conditions.includes('Enf. renal crónica') ? 76 : 8 + i % 22;
  const history = {
    ldl: [ldl + 21, ldl + 13, ldl + 18, ldl + 5, ldl + 9, ldl],
    pressure: [systolic + 10, systolic + 4, systolic + 8, systolic - 1, systolic + 3, systolic],
    hba1c: [hba1c + .7, hba1c + .4, hba1c + .6, hba1c + .2, hba1c + .3, hba1c].map(v => +v.toFixed(1)),
    risk: [risk - 4.8, risk - 3.1, risk - 3.9, risk - 1.2, risk - 1.8, risk].map(v => Math.max(1, +v.toFixed(1)))
  };
  const patient = {
    id: 'p' + String(i + 1).padStart(3, '0'), firstName, lastName, name: firstName + ' ' + lastName, age, sex, risk,
    cip: 'DEMO-' + String(10001 + i), conditions, followup, lastTest, initials: firstName[0] + lastName[0],
    phone: '600 000 000', email: normalize(firstName) + '.demo@example.test',
    color: ['sage', 'sand', 'rose', 'blue'][i % 4],
    metrics: { ldl, systolic, diastolic: 82 + i % 8, hba1c, egfr, acr, bmi: +(25.2 + (high ? 4.2 : i % 4)).toFixed(1) }, history,
    factors: [
      { label: 'Presión arterial sistólica', value: systolic + ' mmHg', weight: 89 },
      { label: 'Colesterol LDL', value: ldl + ' mg/dL', weight: 73 },
      { label: conditions.includes('Diabetes tipo 2') ? 'Diabetes tipo 2' : 'Edad', value: conditions.includes('Diabetes tipo 2') ? formatNumber(hba1c, 1) + ' % HbA1c' : age + ' años', weight: 58 },
      { label: 'Función renal (FGe)', value: egfr + ' mL/min/1,73 m²', weight: 39 },
      { label: 'Albuminuria (CAC)', value: acr + ' mg/g', weight: 26 }
    ],
    events: [
      { id: 'diagnosis', date: '2025-03-18', title: conditions.includes('Diabetes tipo 2') ? 'Diagnóstico de diabetes' : 'Valoración inicial', type: 'Antecedente', icon: 'clipboard', description: conditions.includes('Diabetes tipo 2') ? 'Registro de diabetes tipo 2 en la historia del paciente.' : 'Valoración cardiovascular de referencia y registro de antecedentes.' },
      { id: 'lab-previous', date: '2026-02-12', title: 'Analítica de control', type: 'Laboratorio', icon: 'flask', description: 'Control de perfil lipídico, glucemia y función renal.' },
      { id: 'medication', date: '2026-05-21', title: 'Revisión del tratamiento', type: 'Tratamiento', icon: 'pill', description: 'Revisión de la medicación habitual y registro de adherencia en consulta.' },
      { id: 'ecg', date: '2026-08-07', title: 'Electrocardiograma', type: 'Exploración', icon: 'activity', description: 'ECG de control registrado en la consulta de Atención Primaria.' },
      { id: 'lab-latest', date: lastTest, title: 'Última analítica', type: 'Laboratorio', icon: 'flask', description: 'Perfil lipídico, HbA1c, creatinina y cociente albúmina/creatinina.' }
    ],
    notes: [{ id: 'seed-' + i, date: lastTest + 'T09:30:00', author: 'Dra. Carmen Vidal', text: i === 0 ? 'Se revisan los resultados de la última analítica con la paciente. Refiere buena adherencia al tratamiento. Acordamos registrar la presión arterial en casa y revisar la evolución en la próxima consulta.' : 'Revisión de resultados y antecedentes cardiovasculares. Se registra la evolución para el seguimiento en consulta.' }]
  };
  patient.measurements = makeDemoMeasurements(patient, i);
  patient.history.pressure = patient.measurements.systolic.map(point => point.value);
  patient.history.hba1c = patient.measurements.hba1c.map(point => point.value);
  return patient;
});
export function selectPatients(items, filters) {
  const query = normalize(filters.search || '');
  return items.filter(p =>
    (!query || normalize(p.name + ' ' + p.cip).includes(query)) &&
    (!filters.risk || filters.risk === 'all' || riskLevel(p.risk) === filters.risk) &&
    (!filters.sex || filters.sex === 'all' || p.sex === filters.sex) &&
    (!filters.condition || filters.condition === 'all' || p.conditions.includes(filters.condition)) &&
    (!filters.age || filters.age === 'all' || (filters.age === '65plus' ? p.age >= 65 : p.age < 65)) &&
    (!filters.followupOnly || p.followup)
  ).sort((a, b) => {
    switch (filters.sort) {
      case 'risk-asc': return a.risk - b.risk;
      case 'name': return a.name.localeCompare(b.name, 'es');
      case 'age': return b.age - a.age;
      case 'recent': return b.lastTest.localeCompare(a.lastTest);
      default: return b.risk - a.risk;
    }
  });
}

