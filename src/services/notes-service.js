// Notas de consulta.
//
// HOY: notas de ejemplo de cada paciente + notas nuevas guardadas en localStorage.
// MAÑANA (backend): leer y guardar con api-client.js (api.getNotes / api.createNote / api.updateNote).
import { readStorage, saveStorage, STORAGE_KEYS } from './storage.js';

const storedNotes = readStorage(STORAGE_KEYS.notes, {});
const savedNotes = storedNotes && typeof storedNotes === 'object' && !Array.isArray(storedNotes) ? storedNotes : {};

// Notas del paciente, de la más reciente a la más antigua.
export function notesFor(p) {
  return [...(Array.isArray(savedNotes[p.id]) ? savedNotes[p.id].filter(n => n && typeof n.text === 'string' && typeof n.id === 'string' && typeof n.date === 'string') : []), ...p.notes]
    .sort((a, b) => b.date.localeCompare(a.date));
}

// Crea una nota nueva o actualiza la que se está editando. Devuelve si se ha podido guardar.
export function saveNote(patientId, text, editingId) {
  const list = Array.isArray(savedNotes[patientId]) ? savedNotes[patientId] : [];
  if (editingId) { const note = list.find(n => n.id === editingId); if (note) { note.text = text; note.date = new Date().toISOString(); } }
  else list.unshift({ id: crypto.randomUUID(), text, author: 'Dra. Carmen Vidal', date: new Date().toISOString() });
  savedNotes[patientId] = list;
  return saveStorage(STORAGE_KEYS.notes, savedNotes);
}
