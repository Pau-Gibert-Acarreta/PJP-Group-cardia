// Búsqueda, filtros y ordenación del listado de pacientes. Función pura: no modifica la lista recibida.
// El filtro de riesgo usa la clasificación final (la ajustada por el médico si existe); el orden usa la probabilidad.
import { normalize } from '../utils/text.js';
import { effectiveRiskLevel } from './risk.js';

export function selectPatients(items, filters) {
  const query = normalize(filters.search || '');
  return items.filter(p =>
    (!query || normalize(p.name + ' ' + p.cip).includes(query)) &&
    (!filters.risk || filters.risk === 'all' || effectiveRiskLevel(p) === filters.risk) &&
    (!filters.sex || filters.sex === 'all' || p.sex === filters.sex) &&
    (!filters.condition || filters.condition === 'all' || p.conditions.includes(filters.condition)) &&
    (!filters.age || filters.age === 'all' || (filters.age === '65plus' ? p.age >= 65 : p.age < 65)) &&
    (!filters.followupOnly || p.followup)
  ).sort((a, b) => {
    switch (filters.sort) {
      case 'risk-asc': return a.risk - b.risk;
      case 'name': return a.name.localeCompare(b.name, 'es');
      case 'age': return b.age - a.age;
      case 'recent': return b.lastTest.localeCompare(a.lastTest);
      default: return b.risk - a.risk;
    }
  });
}
