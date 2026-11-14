// Etiqueta de nivel de riesgo (Alto, Medio, Bajo) con su punto de color.
import { RISK_LABELS } from '../../domain/risk.js';

export const riskBadge = level =>
  '<span class="risk-badge ' + level + '"><span class="dot"></span>' + RISK_LABELS[level] + '</span>';
