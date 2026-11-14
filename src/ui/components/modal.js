// Ventana modal única de la aplicación (<dialog id="modal"> en index.html).
import { $ } from '../dom.js';
import { icon } from '../icons.js';

export function openModal(title, body, wide = false) {
  const modal = $('#modal'); modal.className = wide ? 'wide-dialog' : '';
  modal.innerHTML = '<div class="modal-heading"><h2 id="modal-title">' + title + '</h2><button class="icon-button" data-action="close-modal" aria-label="Cerrar ventana">' + icon('close') + '</button></div>' + body;
  if (!modal.open) modal.showModal();
}

export const closeModal = () => $('#modal').close();
