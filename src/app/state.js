// Estado de la interfaz (qué se ve y cómo) y configuración clínica cargada al arrancar.
// Es el único estado mutable de la app: las vistas lo leen y app/actions.js lo modifica.

export const defaultFilters = () => ({ search: '', risk: 'all', sex: 'all', condition: 'all', age: 'all', followupOnly: false, sort: 'risk-desc' });

export const state = {
  filters: defaultFilters(),
  page: 1,
  perPage: 8,
  nav: 'patients',     // patients | priority | followup
  topK: 3,             // variables explicativas visibles en la ficha
  chart: 'ldl',        // clave de CHART_OPTIONS (ui/components/chart.js)
  period: '12',        // meses de la gráfica
  drafts: {},          // borradores de notas por paciente
  noteEditing: null    // id de la nota en edición
};

// Configuración de config/indicators.json y config/finding-rules.json.
export const clinical = { config: null, ruleConfig: null };
