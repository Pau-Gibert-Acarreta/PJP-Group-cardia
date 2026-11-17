# Búsqueda de modelos CoxPH (equipo)

Resultados de la búsqueda de pipelines de supervivencia del equipo, tal cual se generaron. La búsqueda fue un *agentic pipeline search*: un bucle con un LLM que proponía, entrenaba y puntuaba pipelines; el mejor quedó como Champion provisional antes de montar el reentrenamiento programado. Se conservan como registro auditable de la búsqueda.

| Archivo | Contenido |
| --- | --- |
| `code/candidate_*.py` | Los 48 pipelines probados (`build_pipeline()`) |
| `search_log.csv`, `search_log.jsonl` | Configuración, AUC de CV por fold y tiempo de cada candidato |
| `top5_test.csv` | Los 5 mejores por CV con su AUC de test |
| `best_pipeline.py` | El ganador (candidato 38): es el que usa el reentrenamiento (`cardia_ml/train.py`) |
| `test_predictions.csv` | Predicciones del modelo ganador en los 454 pacientes de test (el servicio las reproduce exactamente) |
| `score_progress_coxph.png` | Evolución del score durante la búsqueda |

Los pipelines importan `pipeline_lib_pl` y `surv_models`, que están en `ml/src/`. Para ejecutarlos, añade `ml/src` al `PYTHONPATH`. El modelo entrenado está en `ml/models/coxph_score2_v1.joblib`.

Los datos que usaba la búsqueda (visitas 1-3, 40-69 años, sin diabetes ni CHD o ictus previos, pacientes fuera de test; y = [evento amplio a 10 años, días]) se obtienen ahora de la base de datos con `cardia_ml.data.training_set()`.
