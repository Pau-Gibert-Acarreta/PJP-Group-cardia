# Reglas de hallazgos (v2)

Referencias de [src/config/finding-rules.json](../src/config/finding-rules.json). Las reglas las aplican igual el frontend (`src/domain/findings.js`) y el backend (`backend/app/rules_engine.py`).

| id | Criterio | Gravedad | Referencia |
| --- | --- | --- | --- |
| presion-sistolica-grado-3 | PAS ≥ 180 mmHg: hipertensión grado 3. | warning | ESH 2023, [10.1097/HJH.0000000000003480](https://doi.org/10.1097/HJH.0000000000003480) |
| presion-diastolica-grado-3 | PAD ≥ 110 mmHg: hipertensión grado 3. | warning | ESH 2023, [10.1097/HJH.0000000000003480](https://doi.org/10.1097/HJH.0000000000003480) |
| colesterol-total-extremo | CT ≥ 310 mg/dL: investigar hipercolesterolemia familiar en adultos sin tratamiento. | warning | ESC/EAS 2019, [10.1093/eurheartj/ehz455](https://doi.org/10.1093/eurheartj/ehz455) |
| hdl-bajo | HDL < 40 mg/dL. | attention | ESC/EAS 2019, [10.1093/eurheartj/ehz455](https://doi.org/10.1093/eurheartj/ehz455) |
| hba1c-rango-diabetico | HbA1c ≥ 6,5 %: umbral diagnóstico; requiere confirmación si no hay hiperglucemia inequívoca. | attention | ADA Standards of Care 2026, sección 2, [10.2337/dc26-S002](https://doi.org/10.2337/dc26-S002) |
| hba1c-hiperglucemia-severa | HbA1c > 10 %: considerar insulina en diabetes tipo 2 según el contexto. | warning | ADA Standards of Care 2026, sección 9, [10.2337/dc26-S009](https://doi.org/10.2337/dc26-S009) |
| acr-albuminuria-a3 | ACR > 300 mg/g: albuminuria severamente aumentada (A3). | warning | KDIGO 2024, [10.1016/j.kint.2023.10.018](https://doi.org/10.1016/j.kint.2023.10.018) |
| acr-duplicacion | ACR ≥ 30 mg/g y aumento ≥ 100 % respecto a la anterior: supera la variabilidad analítica. | warning | KDIGO 2024, Practice Point 2.1.5, [10.1016/j.kint.2023.10.018](https://doi.org/10.1016/j.kint.2023.10.018) |
| egfr-descenso-significativo | Descenso de eGFR > 20 % respecto a la anterior: requiere evaluación. | warning | KDIGO 2024, Practice Point 2.1.3, [10.1016/j.kint.2023.10.018](https://doi.org/10.1016/j.kint.2023.10.018) |
| egfr-menor-30 | eGFR < 30 mL/min/1,73 m²: categorías G4-G5. | warning | KDIGO 2024, [10.1016/j.kint.2023.10.018](https://doi.org/10.1016/j.kint.2023.10.018) |
| aki-creatinina-048h | Creatinina +0,3 mg/dL en ≤ 48 h (`maxIntervalDays: 2`): criterio de AKI. | warning | KDIGO 2012 AKI, 2.1.1, [10.1038/kisup.2012.1](https://doi.org/10.1038/kisup.2012.1) |
| aki-creatinina-150-7dias | Creatinina +50 % en ≤ 7 días (`maxIntervalDays: 7`): criterio de AKI. | warning | KDIGO 2012 AKI, 2.1.1, [10.1038/kisup.2012.1](https://doi.org/10.1038/kisup.2012.1) |

## Limitaciones conocidas

- **Hacen falta dos mediciones.** El motor solo evalúa una regla si la variable tiene al menos dos valores, también en las de umbral absoluto (`current`). Un paciente con un único examen no genera hallazgos.
- **HDL sin distinción por sexo.** La guía usa < 40 mg/dL en hombres y < 50 mg/dL en mujeres; el motor no conoce el sexo, así que se aplica 40 a todos.
- **HbA1c ≥ 6,5 % no sabe si ya hay diagnóstico.** En pacientes con diabetes conocida marcará siempre; es un criterio diagnóstico, no de control.
- **AKI necesita pruebas cercanas.** Las dos reglas de creatinina solo saltan con mediciones separadas como mucho 2 o 7 días; con los exámenes de Framingham (años de diferencia) nunca se cumplen.
- Las referencias proceden de una búsqueda asistida por IA y deben revisarse antes de cualquier uso clínico.
