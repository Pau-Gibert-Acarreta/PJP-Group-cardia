// Ventana para que el médico ajuste la clasificación de riesgo (alto, medio, bajo).
// La probabilidad del modelo se muestra como referencia y no se puede editar.
import { riskLevel, effectiveRiskLevel, isRiskOverridden, RISK_LEVELS, RISK_LABELS } from '../../domain/risk.js';
import { formatNumber as num } from '../../utils/format.js';
import { esc } from '../../utils/text.js';
import { icon } from '../icons.js';
import { openModal } from '../components/modal.js';
import { riskBadge } from '../components/risk-badge.js';

const HINTS = { high: 'Priorizar su revisión', medium: 'Observar su evolución', low: 'Seguimiento habitual' };

function option(level, model, current) {
  return '<label class="risk-option ' + level + '"><input type="radio" name="risk-level" value="' + level + '"' + (level === current ? ' checked' : '') + '>' +
    '<span class="risk-option-body"><span class="risk-option-title"><span class="dot"></span><strong>' + RISK_LABELS[level] + '</strong>' +
    (level === model ? '<em>Modelo</em>' : '') + '</span><small>' + HINTS[level] + '</small></span></label>';
}

export function openRiskClassification(p) {
  const model = riskLevel(p.risk), current = effectiveRiskLevel(p), overridden = isRiskOverridden(p);
  openModal('Ajustar clasificación de riesgo',
    '<form id="risk-form" class="risk-form" novalidate>' +
    '<div class="risk-form-model"><span>Predicción del modelo</span><div><strong>' + num(p.risk, 1) + ' %</strong>' + riskBadge(model) + '</div>' +
    '<small>' + icon('info') + 'La probabilidad no se puede modificar. Solo cambia la clasificación que se usa para priorizar al paciente.</small></div>' +
    '<fieldset class="risk-options"><legend>Clasificación clínica</legend>' + RISK_LEVELS.map(level => option(level, model, current)).join('') + '</fieldset>' +
    '<label class="risk-reason" for="risk-reason">Motivo del ajuste <small>Obligatorio si la clasificación no coincide con la del modelo</small></label>' +
    '<textarea id="risk-reason" maxlength="500" rows="3" placeholder="Ej.: antecedente familiar de cardiopatía precoz no recogido en el modelo">' + esc(overridden ? p.riskOverride.reason : '') + '</textarea>' +
    '<p class="risk-form-error" id="risk-form-error" role="alert"></p>' +
    '<div class="modal-footer">' +
    (overridden ? '<button type="button" class="button secondary restore-risk" data-action="restore-risk">' + icon('reset') + ' Volver a la del modelo</button>' : '') +
    '<button type="button" class="button secondary" data-action="close-modal">Cancelar</button>' +
    '<button type="submit" class="button primary">Guardar clasificación</button></div></form>');
}
