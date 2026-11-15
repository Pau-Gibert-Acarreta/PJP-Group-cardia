"""ETL de datos (bloque 1 del diagrama: fuentes heterogéneas -> limpieza y normalización -> base de datos).

- sources.py: construye, una sola vez, las fuentes separadas por origen a partir de raw.csv
  y de la generación de datos sintéticos (data/sources/*.csv).
- load.py: lee esas fuentes, las transforma y carga la base de datos.
"""
