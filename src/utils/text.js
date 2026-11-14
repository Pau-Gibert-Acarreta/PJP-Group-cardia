// Utilidades de texto compartidas.

// Escapa texto para insertarlo de forma segura en HTML.
export const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Minúsculas y sin tildes, para búsquedas.
export const normalize = value => String(value).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
