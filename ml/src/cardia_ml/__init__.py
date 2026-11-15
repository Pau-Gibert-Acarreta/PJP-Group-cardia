"""Cardia ML: entrenamiento periódico (bloque 4A) y Motor de Riesgo + XAI (bloque 4B).

- data.py: lee de la base de datos exactamente las variables que el equipo leía de
  raw.csv / parquet (mismos nombres, códigos y unidades).
- train.py: reentrena el pipeline ganador de la búsqueda y lo compara con el Champion.
- model.py: carga el modelo congelado y calcula la probabilidad a 10 años.
- explain.py: valores SHAP exactos por paciente.
"""
