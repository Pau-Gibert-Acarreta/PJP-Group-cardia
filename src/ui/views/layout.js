// Estructura común: barra lateral, barra superior, contenido principal (#main-content) y pie.
import { state } from '../../app/state.js';
import { icon } from '../icons.js';
import { getPatients } from '../../services/patient-service.js';
import { effectiveRiskLevel } from '../../domain/risk.js';

function navItem(key, glyph, label, counter) {
  return '<button class="nav-item ' + (state.nav === key ? 'active' : '') + '" data-action="nav" data-nav="' + key + '">' + icon(glyph) + '<span>' + label + '</span>' + counter + '</button>';
}

function sidebar() {
  return '<aside class="sidebar">' +
    '<a class="brand" href="#" aria-label="Cardia, inicio"><span class="brand-symbol">' + icon('activity') + '</span><span>cardia<span class="brand-dot">.</span></span></a>' +
    '<div class="nav-label">ESPACIO CLÍNICO</div>' +
    '<nav aria-label="Navegación principal">' +
    navItem('patients', 'users', 'Pacientes', '<span class="nav-count">' + new Intl.NumberFormat('es-ES').format(getPatients().length) + '</span>') +
    navItem('priority', 'heart', 'Prioridad clínica', '<span class="priority-count">' + getPatients().filter(p => effectiveRiskLevel(p) === 'high').length + '</span>') +
    navItem('followup', 'bookmark', 'En seguimiento', '') +
    '</nav></aside>';
}

function topbar(onPatientPage) {
  return '<header class="topbar">' +
    '<div class="breadcrumb"><span>Área clínica</span>' + icon('chevron') +
    (onPatientPage ? '<a href="#">Pacientes</a>' + icon('chevron') + '<strong>Ficha del paciente</strong>' : '<strong>Pacientes</strong>') + '</div>' +
    '<div class="topbar-right">' +
    '<button class="icon-button notification" aria-label="Ver avisos de la demo" data-action="notifications">' + icon('bell') + '<i></i></button>' +
    '<button class="doctor" data-action="profile"><span class="doctor-avatar">CV</span><span><strong>Dra. Carmen Vidal</strong><small>Medicina de familia</small></span>' + icon('down') + '</button>' +
    '</div></header>';
}


export function layout(onPatientPage) {
  return sidebar() +
    '<div class="main-shell">' + topbar(onPatientPage) + '<main id="main-content" class="content"></main>' + '</div>';
}
