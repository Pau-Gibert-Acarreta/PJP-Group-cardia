// Ventanas informativas: interpretación del riesgo, acerca de, avisos, perfil y restablecer la demo.
import { icon } from '../icons.js';
import { openModal } from '../components/modal.js';
import { getPatients } from '../../services/patient-service.js';
import { effectiveRiskLevel } from '../../domain/risk.js';

export function openRiskInfo() {
  openModal('Cómo leer el riesgo', '<div class="info-body">' +
    '<p>El porcentaje es la <strong>probabilidad estimada de un evento cardiovascular en los próximos 10 años</strong> (infarto, angina, enfermedad coronaria o ictus). La calcula un modelo de Cox entrenado con el estudio de Framingham a partir de edad, sexo, tabaquismo, presión sistólica, colesterol total y HDL.</p>' +
    '<div class="risk-explanation"><span class="risk-badge low"><i class="dot"></i>Bajo</span><span>Menos del 10 %</span><span class="risk-badge medium"><i class="dot"></i>Medio</span><span>Desde el 10 % hasta menos del 20 %</span><span class="risk-badge high"><i class="dot"></i>Alto</span><span>20 % o más</span></div>' +
    '<p>Las barras muestran cuánto aporta cada variable a la estimación de este paciente (valores SHAP): ↑ la aumenta y ↓ la reduce respecto a un paciente medio. Los umbrales del semáforo son ilustrativos.</p>' +
    '<div class="modal-note">' + icon('info') + ' Prototipo para presentación. No utilizar para tomar decisiones clínicas.</div></div>');
}

export function openAbout() {
  openModal('Más foco en el paciente', '<div class="info-body">' +
    '<p><strong>Cardia</strong> es una primera propuesta para conectar antecedentes, analíticas y evolución en una consulta de Atención Primaria.</p>' +
    '<p>Explora ' + new Intl.NumberFormat('es-ES').format(getPatients().length) + ' pacientes del estudio de Framingham (con nombres y algunas analíticas sintéticas), prioriza por riesgo, consulta pruebas y registra notas.</p>' +
    '<div class="about-feature">' + icon('flask') + '<div><strong>Una demo para aprender</strong><p>El riesgo lo calcula un modelo de Cox entrenado con el estudio de Framingham (AUC 0,66 en test), con su explicación SHAP. Las mediciones, la historia, las notas y el seguimiento vienen de la base de datos.</p></div></div>' +
    '<p>Las notas y el seguimiento se guardan en el servidor. Los ajustes de la clasificación de riesgo se guardan en este navegador y puedes restablecerlos.</p>' +
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
