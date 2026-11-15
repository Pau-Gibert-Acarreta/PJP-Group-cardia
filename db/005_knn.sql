-- =============================================================================
-- Cardia · KNN de pacientes similares
--
-- Run after 001-004 (from the repository root):
--   psql -d cardia -v ON_ERROR_STOP=1 -f db/005_knn.sql
-- Then build the index from backend/:
--   uv run python -m app.jobs.build_knn_index
--
-- 1. exam_embedding.embedding pasa de vector(16) a vector(20): estado clínico +
--    tendencias por examen, solo con variables originales de Framingham
--    (lista en backend/app/knn/features.py).
-- 2. embedding_model guarda, por versión, las variables, sus pesos y el
--    escalador (media y desviación) con el que se construyeron los vectores.
--    Un vector de consulta solo es comparable si usa la misma versión.
-- Idempotente: se puede ejecutar más de una vez.
-- =============================================================================

SET search_path = cardia, public;
BEGIN;

-- Los vectores de otra dimensión no son compatibles con el nuevo formato.
DO $$
BEGIN
    IF (SELECT atttypmod FROM pg_attribute
        WHERE attrelid = 'cardia.exam_embedding'::regclass AND attname = 'embedding') <> 20 THEN
        DELETE FROM exam_embedding;
        DROP INDEX IF EXISTS exam_embedding_hnsw_idx;
        ALTER TABLE exam_embedding ALTER COLUMN embedding TYPE vector(20);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS exam_embedding_hnsw_idx ON exam_embedding
    USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS embedding_model (
    version      text        PRIMARY KEY,
    dimensions   smallint    NOT NULL,
    -- [{ "key": "systolic", "weight": 2.5, "mean": 136.3, "std": 22.8 }, ...] en el orden del vector
    features     jsonb       NOT NULL,
    exams        integer     NOT NULL,     -- estados indexados
    created_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE embedding_model IS
    'Escalador y pesos de cada versión de exam_embedding. El vector guardado es z-score * sqrt(peso), así la distancia L2 es la euclídea ponderada.';

COMMIT;
