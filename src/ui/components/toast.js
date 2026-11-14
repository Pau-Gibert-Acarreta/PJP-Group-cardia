// Aviso flotante temporal (<div id="toast"> en index.html).
import { $ } from '../dom.js';

export function toast(message) {
  $('#toast').textContent = message; $('#toast').classList.add('visible');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').classList.remove('visible'), 3500);
}
