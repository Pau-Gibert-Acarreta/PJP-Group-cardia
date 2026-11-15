-- =============================================================================
-- Cardia · Smoke test for the data layer
--
-- Run after loading the data (backend: python -m app.jobs.load_sources --reset):
--   psql -d cardia -v ON_ERROR_STOP=1 -f db/003_smoke_test.sql
--
-- Stops at the first failed check. Everything runs in one transaction that is
-- rolled back, so the database is left untouched.
-- =============================================================================

SET search_path = cardia, public;
BEGIN;

-- 1. Load: row counts match raw.csv -------------------------------------------
DO $$
BEGIN
    ASSERT (SELECT count(*) FROM patient)         = 4434,  'patient: expected 4434 rows';
    ASSERT (SELECT count(*) FROM patient_outcome) = 4434,  'patient_outcome: expected 4434 rows';
    ASSERT (SELECT count(*) FROM exam)            = 11627, 'exam: expected 11627 rows';
    ASSERT (SELECT count(*) FROM measurement WHERE indicator_code IN
            ('systolic', 'diastolic', 'heart_rate', 'bmi', 'total_cholesterol', 'hdl_cholesterol', 'ldl', 'glucose')) = 73908,
           'measurement: expected 73908 non-missing values from raw.csv';
    ASSERT (SELECT count(*) FROM measurement WHERE indicator_code IN ('hba1c', 'serum_creatinine', 'egfr', 'acr'))
           = 4 * 11627, 'measurement: expected 4 synthetic lab values per exam';
    ASSERT (SELECT count(*) FROM ingestion_batch WHERE source_uri LIKE 'file://data/sources/%') = 6,
           'ingestion_batch: expected one batch per source';
    ASSERT (SELECT count(*) FROM exam_features)   = 11627, 'exam_features: expected one row per exam';
    ASSERT (SELECT count(*) FROM patient_overview) = 4434, 'patient_overview: expected one row per patient';
    ASSERT NOT EXISTS (SELECT 1 FROM exam GROUP BY patient_id, period HAVING count(*) > 1),
           'exam: a patient has two rows for the same period';
    RAISE NOTICE 'ok 1 - row counts';
END $$;

-- 2. Load: values survive the round trip (first patient of raw.csv) ------------
DO $$
DECLARE f exam_features;
BEGIN
    SELECT * INTO f FROM exam_features WHERE patient_id = 2448 AND period = 3;
    ASSERT f.days_since_baseline = 4628 AND f.age_years = 52,   'exam 2448/3: TIME or AGE mismatch';
    ASSERT f.systolic = 121 AND f.diastolic = 66,               'exam 2448/3: blood pressure mismatch';
    ASSERT f.hdl_cholesterol = 31 AND f.ldl = 178,              'exam 2448/3: HDL/LDL mismatch';
    ASSERT f.bmi IS NULL,                                       'exam 2448/3: missing BMI must stay missing';
    ASSERT (SELECT cvd AND days_to_cvd = 6438 FROM patient_outcome WHERE patient_id = 2448),
           'outcome 2448: CVD mismatch';
    RAISE NOTICE 'ok 2 - spot check against raw.csv';
END $$;

-- 3. TimescaleDB: the three series are hypertables -----------------------------
DO $$
BEGIN
    ASSERT (SELECT count(*) FROM timescaledb_information.hypertables
            WHERE hypertable_schema = 'cardia'
              AND hypertable_name IN ('exam', 'measurement', 'risk_prediction')) = 3,
           'expected exam, measurement and risk_prediction to be hypertables';
    ASSERT (SELECT count(*) FROM timescaledb_information.chunks
            WHERE hypertable_schema = 'cardia' AND hypertable_name = 'measurement') > 1,
           'measurement: expected the load to span several chunks';
    RAISE NOTICE 'ok 3 - hypertables and chunks';
END $$;

-- 4. pgvector: insert, nearest-neighbour query, HNSW index is usable -----------
DO $$
DECLARE nearest bigint;
BEGIN
    INSERT INTO exam_embedding (patient_id, exam_time, embedding_version, embedding)
    SELECT patient_id, exam_time, 'smoke',
           ('[' || array_to_string(ARRAY(SELECT (patient_id % (i + 7))::float / (i + 7)
                                         FROM generate_series(1, 20) i), ',') || ']')::vector
    FROM exam WHERE period = 1 LIMIT 500;

    SELECT e.patient_id INTO nearest
    FROM exam_embedding e
    WHERE e.embedding_version = 'smoke'
    ORDER BY e.embedding <-> (SELECT embedding FROM exam_embedding
                              WHERE patient_id = 2448 AND embedding_version = 'smoke')
    LIMIT 1;
    ASSERT nearest = 2448, 'KNN: a vector must be its own nearest neighbour';

    ASSERT EXISTS (SELECT 1 FROM pg_indexes
                   WHERE schemaname = 'cardia' AND indexname = 'exam_embedding_hnsw_idx'
                     AND indexdef LIKE '%USING hnsw%'),
           'HNSW index on exam_embedding is missing';
    RAISE NOTICE 'ok 4 - pgvector insert and KNN';
END $$;

-- 5. Constraints reject bad writes ---------------------------------------------
DO $$
BEGIN
    BEGIN
        INSERT INTO risk_prediction (patient_id, target, predicted_at, model_name, model_version,
                                     probability, horizon_years, input_exam_time, features)
        VALUES (2448, 'cv', now(), 'smoke', 'v0', 1.5, 10, now(), '{}');
        RAISE EXCEPTION 'probability > 1 was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO measurement (patient_id, indicator_code, measured_at, value)
        VALUES (2448, 'not_an_indicator', now(), 1);
        RAISE EXCEPTION 'unknown indicator was accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    INSERT INTO risk_classification_override (patient_id, level, model_level, reason, author)
    VALUES (2448, 'high', 'low', 'smoke', 'smoke');
    BEGIN
        INSERT INTO risk_classification_override (patient_id, level, model_level, reason, author)
        VALUES (2448, 'medium', 'low', 'smoke', 'smoke');
        RAISE EXCEPTION 'two active overrides for one patient were accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    RAISE NOTICE 'ok 5 - constraints';
END $$;

-- 6. Application path: prediction + follow-up show up in the list view ---------
DO $$
DECLARE o patient_overview;
BEGIN
    INSERT INTO risk_prediction (patient_id, target, predicted_at, model_name, model_version,
                                 probability, horizon_years, input_exam_time, features, shap_top_k)
    VALUES (2448, 'cv', now() - interval '1 day', 'smoke', 'v0', 0.10, 10, now(), '{}', '[]'),
           (2448, 'cv', now(),                    'smoke', 'v0', 0.25, 10, now(), '{}',
            '[{"feature": "systolic", "value": 121, "contribution": 0.04}]');
    INSERT INTO patient_followup VALUES (2448, true, 'smoke');

    SELECT * INTO o FROM patient_overview WHERE patient_id = 2448;
    ASSERT o.cv_risk = 0.25,               'patient_overview: must show the latest prediction';
    ASSERT o.followup,                     'patient_overview: follow-up flag not visible';
    ASSERT o.risk_override_level = 'high', 'patient_overview: active override not visible';
    ASSERT o.age = 52,                     'patient_overview: age must come from the latest exam';
    RAISE NOTICE 'ok 6 - list view';
END $$;

-- 7. Frontend contract: measurements[field] = [{ value, date, unit }] ----------
SELECT m.indicator_code AS field,
       jsonb_agg(jsonb_build_object('value', m.value, 'date', m.measured_at::date, 'unit', i.unit)
                 ORDER BY m.measured_at) AS series
FROM measurement m JOIN indicator i ON i.code = m.indicator_code
WHERE m.patient_id = 2448
GROUP BY m.indicator_code;

ROLLBACK;
\echo 'All checks passed.'
