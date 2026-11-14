# Cardia

Prototipo frontend de una consulta de Atención Primaria para explorar el riesgo cardiovascular con 24 pacientes ficticios. Incluye búsqueda, filtros, ordenación, fichas individuales, historial de pruebas, gráficas, indicadores, hallazgos y notas locales.

## Ejecutar

Requiere Node.js 20 o posterior. Desde esta carpeta:

```sh
node scripts/serve.mjs
```

Abre [http://localhost:5173](http://localhost:5173). No hace falta instalar paquetes. El servidor solo entrega archivos estáticos y escucha en la interfaz local. No es un backend clínico. También puedes usar `npm run dev` si tu terminal dispone de Node y npm.

En Windows, si el repositorio está en una ruta UNC de WSL, ejecuta directamente `node scripts/serve.mjs` desde PowerShell; así evitas la restricción de rutas UNC de CMD al ejecutar scripts npm. Desde WSL necesitas una instalación de Node disponible en esa distribución.

## Configuración clínica

- [Indicadores y columnas](src/config/indicators.json): nombres, claves de datos, unidades, decimales, orden de las filas y columnas del resumen.
- [Reglas de hallazgos](src/config/finding-rules.json): añade, modifica o desactiva alertas sin editar el frontend.
- [Contrato de datos y configuración](docs/data-contract.md): estructura de las mediciones y ejemplos de reglas.
- [Datos ficticios](src/data/demo/): pacientes e historiales de ejemplo, incluidos cambios relevantes y datos incompletos.
- [Arquitectura del frontend](docs/arquitectura.md): qué hay en cada carpeta, cómo fluye la información y cómo conectar el backend.

Las claves técnicas son provisionales porque todavía no se ha facilitado el esquema de la base de datos. El campo `field` de un indicador y de una regla identifica la misma variable dentro de `patient.measurements`. Cuando exista ese esquema, el adaptador de datos deberá entregar esas claves o se deberán actualizar los JSON. No hay ninguna conexión a una base de datos ni a un modelo de ML.

## Comprobar

```sh
node scripts/check.mjs
```

Comprueba la sintaxis de los módulos y ejecuta las pruebas de búsqueda, filtros, historiales, cambios, reglas, datos ausentes y categorías KDIGO. También está disponible `npm run check`.

## Notas de la demo

El riesgo y los factores explicativos están simulados. Las reglas de hallazgos usan umbrales ilustrativos pendientes de validación clínica. Las categorías G/A de KDIGO se obtienen de eGFR y ACR y no establecen un diagnóstico de enfermedad renal crónica.

Las notas de consulta y el seguimiento se guardan en `localStorage` de este navegador. Se pueden restablecer desde “Acerca de la demo”. Todos los recursos de la interfaz son locales; las únicas solicitudes del frontend son los dos JSON de configuración.

Las instrucciones originales del repositorio de la hackathon se conservan en [docs/hackathon-repository.md](docs/hackathon-repository.md).
