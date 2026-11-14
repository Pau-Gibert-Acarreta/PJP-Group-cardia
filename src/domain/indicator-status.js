// Estado clínico de un valor y de su cambio, para colorear la interfaz (verde, amarillo, naranja, rojo).
// Las bandas y la dirección favorable ("better") se configuran en config/indicators.json.

// Colores por categoría G de KDIGO: ≥60 verde, 45–59 amarillo, 30–44 naranja, <30 rojo.
export function egfrLevel(value) {
  if (!Number.isFinite(value)) return 'none';
  return value >= 60 ? 'ok' : value >= 45 ? 'mild' : value >= 30 ? 'moderate' : 'severe';
}

// Tono (green, yellow, orange, red) de un valor según las bandas configuradas en indicators.json.
export function valueTone(value, definition) {
  if (!Number.isFinite(value) || !Array.isArray(definition?.bands)) return 'neutral';
  let tone = 'neutral';
  for (const band of definition.bands) if (value >= band.from) tone = band.tone;
  return tone;
}

// Dirección clínica del cambio: worse, better o stable.
export function changeDirection(summary) {
  if (!summary.delta || !summary.better) return 'stable';
  const rising = summary.delta > 0;
  return (summary.better === 'lower') === rising ? 'worse' : 'better';
}

export function deltaTone(summary) {
  const direction = changeDirection(summary);
  if (direction === 'better') return 'green';
  if (direction === 'stable') return 'neutral';
  return ['red', 'orange'].includes(valueTone(summary.latest?.value, summary)) ? 'red' : 'yellow';
}
