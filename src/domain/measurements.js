// Series de mediciones de un paciente y su resumen (último valor, anterior, cambio, mínimo y máximo).
// Trabaja sobre datos normalizados: patient.measurements[field] = [{ value, date, unit? }].

function timestamp(date) {
  if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:$|T)/.test(date)) return NaN;
  const day = date.slice(0, 10);
  // Evita aceptar fechas imposibles que Date normaliza (p. ej. 30 de febrero).
  const parsedDay = new Date(day + 'T00:00:00Z');
  if (!Number.isFinite(parsedDay.getTime()) || parsedDay.toISOString().slice(0, 10) !== day) return NaN;
  return Date.parse(date.length === 10 ? day + 'T00:00:00Z' : date);
}

// Mediciones válidas, sin duplicados por fecha y ordenadas de la más antigua a la más reciente.
export function getSeries(patient, definition) {
  const field = typeof definition === 'string' ? definition : definition.field;
  const expectedUnit = typeof definition === 'object' ? definition.unit : undefined;
  const records = patient.measurements?.[field];
  if (!Array.isArray(records)) return [];
  const unique = new Map();
  for (const record of records) {
    if (!record || typeof record.value !== 'number' || !Number.isFinite(record.value) ||
        (expectedUnit && record.unit && record.unit !== expectedUnit)) continue;
    const time = timestamp(record.date);
    if (Number.isFinite(time)) unique.set(time, { value: record.value, date: record.date, time });
  }
  return [...unique.values()].sort((a, b) => a.time - b.time);
}

const precise = value => Number(value.toPrecision(12));

export function summarizeIndicator(patient, definition) {
  const series = getSeries(patient, definition);
  const latest = series.at(-1) ?? null, previous = series.at(-2) ?? null;
  return {
    ...definition, series, latest, previous,
    delta: latest && previous ? precise(latest.value - previous.value) : 0,
    percentChange: latest && previous && previous.value !== 0 ? precise((latest.value - previous.value) / Math.abs(previous.value) * 100) : null,
    min: series.length ? Math.min(...series.map(point => point.value)) : null,
    max: series.length ? Math.max(...series.map(point => point.value)) : null
  };
}

export function getIndicatorRows(patient, config) {
  return config.indicators.map(definition => summarizeIndicator(patient, definition));
}
