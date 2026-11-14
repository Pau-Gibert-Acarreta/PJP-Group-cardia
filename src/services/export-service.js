// Exportación del listado filtrado a CSV (separador ";" y BOM para que Excel respete las tildes).
import { selectPatients } from '../domain/patient-filters.js';
import { riskLevel, effectiveRiskLevel, isRiskOverridden, RISK_LABELS } from '../domain/risk.js';
import { summarizeIndicator } from '../domain/measurements.js';
import { patientKdigo } from '../domain/kdigo.js';
import { formatNumber as num } from '../utils/format.js';

export function buildPatientsCsv(patients, filters, config) {
  const definitions = config.overviewFields.map(field => config.indicators.find(item => item.field === field));
  const header = ['Identificador', 'Riesgo simulado (%)', 'Nivel de riesgo', 'Nivel según el modelo', 'Motivo del ajuste clínico', 'Paciente', 'Edad', 'Sexo', 'KDIGO (eGFR / ACR)', ...definitions.map(item => item.label + ' (' + item.unit + ')'), 'Fecha última prueba'];
  const rows = selectPatients(patients, filters).map(p => [
    p.cip, num(p.risk, 1), RISK_LABELS[effectiveRiskLevel(p)], RISK_LABELS[riskLevel(p.risk)], isRiskOverridden(p) ? p.riskOverride.reason : '', p.name, p.age, p.sex, patientKdigo(p, config) || '',
    ...definitions.map(item => { const latest = summarizeIndicator(p, item).latest; return latest ? num(latest.value, item.decimals) : ''; }),
    p.lastTest
  ]);
  return '﻿' + [header, ...rows].map(row => row.map(v => '"' + String(v).replaceAll('"', '""') + '"').join(';')).join('\r\n');
}

export function downloadCsv(csv, filename) {
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
