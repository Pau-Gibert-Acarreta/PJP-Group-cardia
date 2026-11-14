// Formato de valores clínicos para mostrar en pantalla.
import { formatNumber as num, formatDate as date } from '../utils/format.js';

export const displayDate = point => point ? date(point.date.slice(0, 10)) : 'Sin fecha';

export function formattedValue(value, definition) { return num(value, definition.decimals); }

// Cambio con signo: "+20", "−6" o "0".
export function formatDelta(summary) {
  return (summary.delta > 0 ? '+' : summary.delta < 0 ? '−' : '') + num(Math.abs(summary.delta), summary.decimals);
}
