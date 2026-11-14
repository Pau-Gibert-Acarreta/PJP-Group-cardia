// Almacenamiento local del navegador (localStorage), tolerante a fallos.
// Si el navegador lo bloquea, la app sigue funcionando y los cambios duran solo la sesión.

let available = true;

export function readStorage(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { available = false; return fallback; }
}

export function saveStorage(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { available = false; return false; }
}

// Lanza una excepción si no se puede acceder al almacenamiento.
export function removeStorage(...keys) {
  keys.forEach(key => localStorage.removeItem(key));
}

export const isStorageAvailable = () => available;

export const STORAGE_KEYS = { notes: 'cardia.notes', followups: 'cardia.followups', riskOverrides: 'cardia.riskOverrides' };
