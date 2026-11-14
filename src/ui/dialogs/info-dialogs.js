// Ventanas informativas: interpretación del riesgo, acerca de, avisos, perfil y restablecer la demo.
import { icon } from '../icons.js';
import { openModal } from '../components/modal.js';
import { getPatients } from '../../services/patient-service.js';
import { effectiveRiskLevel } from '../../domain/risk.js';

export function openRiskInfo() {
  openModal('Cómo leer el riesgo en esta demo', '<div class="info-body">' +
    '<p>El porcentaje representa una <strong>probabilidad ficticia de un evento cardiovascular a 10 años</strong>. Todavía no hay un modelo conectado: se simula en el navegador a partir de la edad y del identificador, solo para probar la interfaz.</p>' +
    '<div class="risk-explanation"><span class="risk-badge low"><i class="dot"></i>Bajo</span><span>Menos del 10 %</span><span class="risk-badge medium"><i class="dot"></i>Medio</span><span>Desde el 10 % hasta menos del 20 %</span><span class="risk-badge high"><i class="dot"></i>Alto</span><span>20 % o más</span></div>' +
    '<p>Estos umbrales son ilustrativos. Las barras de variables también son simuladas y no son una explicación validada de un modelo.</p>' +
    '<div class="modal-note">' + icon('info') + ' Prototipo para presentación. No utilizar para tomar decisiones clínicas.</div></div>');
}

export function openAbout() {
  openModal('Más foco en el paciente', '<div class="info-body">' +
    '<p><strong>Cardia</strong> es una primera propuesta para conectar antecedentes, analíticas y evolución en una consulta de Atención Primaria.</p>' +
    '<p>Explora ' + new Intl.NumberFormat('es-ES').format(getPatients().length) + ' pacientes del estudio de Framingham (con nombres y algunas analíticas sintéticas), prioriza por riesgo, consulta pruebas y registra notas.</p>' +
    '<div class="about-feature">' + icon('flask') + '<div><strong>Una demo para aprender</strong><p>No hay un modelo de machine learning conectado. Las probabilidades y sus contribuciones son simuladas; las mediciones, la historia, las notas y el seguimiento vienen de la base de datos.</p></div></div>' +
    '<p>Las notas y el seguimiento se guardan en el servidor. Los ajustes de la clasificación de riesgo, al ser sobre un riesgo simulado, se guardan solo en este navegador y puedes restablecerlos.</p>' +
    '<button class="button secondary" data-action="reset-demo">' + icon('reset') + ' Restablecer ajustes de riesgo</button></div>');
}

export function openNotifications() {
  openModal('Avisos del cupo',
    '<div class="notification-item"><span class="stat-icon high">' + icon('heart') + '</span><div><h3>' + getPatients().filter(p => effectiveRiskLevel(p) === 'high').length + ' pacientes con riesgo alto</h3><p>Puedes encontrarlos en Prioridad clínica y consultar sus fichas.</p></div></div>' +
    '<div class="notification-item"><span class="stat-icon all">' + icon('flask') + '</span><div><h3>Datos listos para explorar</h3><p>' + new Intl.NumberFormat('es-ES').format(getPatients().length) + ' pacientes con analíticas e historial.</p></div></div>' +
    '<div class="modal-note">' + icon('info') + ' Avisos de ejemplo, sin sincronización clínica.</div>');
}

export function openProfile() {
  openModal('Tu espacio de trabajo',
    '<div class="profile-dialog"><span class="doctor-avatar">CV</span><h3>Dra. Carmen Vidal</h3><p>Medicina de familia · CAP Sant Martí</p><span class="demo-pill">Perfil de demostración</span></div>' +
    '<div class="modal-note">' + icon('shield') + ' Sesión local de ejemplo. No requiere inicio de sesión.</div>');
}

export function openResetConfirm() {
  openModal('Restablecer ajustes de riesgo', '<div class="info-body">' +
    '<p>Se eliminarán los ajustes de clasificación de riesgo guardados en este navegador. Las notas y el seguimiento están en el servidor y no se tocan.</p>' +
    '<div class="modal-footer"><button class="button secondary" data-action="close-modal">Cancelar</button><button class="button primary" data-action="confirm-reset">Restablecer ajustes</button></div></div>');
}
