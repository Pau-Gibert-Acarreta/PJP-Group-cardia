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
  period: 'all',       // meses de la gráfica ('6', '12') o 'all': los exámenes del estudio están separados años
  drafts: {},          // borradores de notas por paciente
  noteEditing: null    // id de la nota en edición
};

// Configuración de config/indicators.json y config/finding-rules.json.
export const clinical = { config: null, ruleConfig: null };
