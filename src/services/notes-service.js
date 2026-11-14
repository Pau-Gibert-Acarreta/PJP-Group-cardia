// Notas de consulta, guardadas en el servidor (Core Backend API).
import { api } from './api-client.js';

// Notas del paciente, de la más reciente a la más antigua (llegan con la ficha).
export function notesFor(p) {
  return [...(p.notes ?? [])].sort((a, b) => b.date.localeCompare(a.date));
}

// Crea una nota nueva o actualiza la que se está editando. Lanza un error si el servidor no la guarda.
export async function saveNote(p, text, editingId) {
  if (editingId) {
    const updated = await api.updateNote(p.id, editingId, text);
    p.notes = (p.notes ?? []).map(n => (n.id === editingId ? updated : n));
  } else {
    const created = await api.createNote(p.id, text);
    p.notes = [created, ...(p.notes ?? [])];
  }
}
