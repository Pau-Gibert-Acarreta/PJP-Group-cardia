// Única capa de datos de ejemplo. Sustituible por un adaptador, sin cambiar las vistas.
export function makeDemoMeasurements(patient, index) {
  const m = patient.metrics;
  const dates = ['2025-12-12', '2026-02-12', '2026-04-16', '2026-06-18', '2026-08-07', patient.lastTest];
  const total = m.ldl + 65 + index % 12, hdl = 43 + index % 17;
  const creatinine = +(0.82 + (100 - m.egfr) * .011).toFixed(2);
  const values = {
    systolic: [...patient.history.pressure],
    diastolic: [m.diastolic + 4, m.diastolic + 2, m.diastolic + 3, m.diastolic + 1, m.diastolic + 2, m.diastolic],
    total_cholesterol: [total + 18, total + 10, total + 14, total + 4, total + 6, total],
    hdl_cholesterol: [hdl - 4, hdl - 3, hdl - 2, hdl - 3, hdl - 1, hdl],
    hba1c: [...patient.history.hba1c],
    acr: [m.acr + 7, m.acr + 6, m.acr + 3, m.acr + 8, m.acr + 4, m.acr],
    serum_creatinine: [creatinine - .12, creatinine - .08, creatinine - .1, creatinine - .05, creatinine - .02, creatinine].map(v => +v.toFixed(2)),
    egfr: [m.egfr + 7, m.egfr + 4, m.egfr + 6, m.egfr + 2, m.egfr + 3, m.egfr],
    ldl: [...patient.history.ldl]
  };
  // Casos para la demo: cambios, estabilidad y datos incompletos.
  if (index === 0) { values.systolic[4] = 128; values.acr[4] = 24; values.hba1c[4] = 6.6; }
  if (index === 1) { values.egfr[4] = 77; values.serum_creatinine[4] = +(creatinine - .4).toFixed(2); }
  if (index === 2) values.diastolic[4] = m.diastolic - 12;
  if (index === 3) values.hba1c[4] = +(m.hba1c - .7).toFixed(1);
  if (index === 23) { values.hdl_cholesterol = []; values.serum_creatinine = [creatinine]; }
  return Object.fromEntries(Object.entries(values).map(([field, series]) => [field, series.map((value, j) => ({ value, date: series.length === 1 ? patient.lastTest : dates[j] }))]));
}

