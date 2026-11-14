// Formato de números y fechas en español (es-ES). Sin dependencias del DOM.

export const formatNumber = (value, digits = 0) =>
  new Intl.NumberFormat('es-ES', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);

export const formatDate = (date, long = false) =>
  new Intl.DateTimeFormat('es-ES', { day: '2-digit', month: long ? 'long' : 'short', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(date + 'T12:00:00Z'));
