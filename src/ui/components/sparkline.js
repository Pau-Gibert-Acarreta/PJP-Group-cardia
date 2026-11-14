// Minigráfica de la evolución del riesgo (p.history.risk). Disponible para la vista de listado.

export function sparkline(p) {
  const values = p.history.risk, min = Math.min(...values) - 1, max = Math.max(...values) + 1;
  const points = values.map((v, i) => (i * 12 + 2) + ',' + (27 - (v - min) / (max - min) * 23)).join(' ');
  return '<svg viewBox="0 0 66 32" class="sparkline" aria-label="Evolución simulada del riesgo"><polyline points="' + points + '" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}
