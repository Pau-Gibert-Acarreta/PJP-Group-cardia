-- =============================================================================
-- Cardia · Synthetic fill for fields the frontend needs but raw.csv lacks
--
-- Run after 002_load_raw_csv.sql (from the repository root):
--   psql -d cardia -v ON_ERROR_STOP=1 -f db/004_synthetic_fill.sql
--
-- Fills, and nothing else:
--   1. patient: first_name, last_name, cip, phone, email   (only where NULL)
--   2. measurement: hba1c, serum_creatinine, egfr, acr      (one value per exam)
--
-- Documents, OCR and every other table are left alone on purpose.
--
-- All values are FAKE. They are deterministic (derived from patient_id with
-- md5, no random()), so a re-run gives the same result, and the script is safe
-- to run twice: it only fills empty fields and skips existing measurements.
-- Synthetic measurements are tagged with source = 'lab' and their own
-- ingestion_batch row (source_uri 'synthetic://004_synthetic_fill').
-- =============================================================================

SET search_path = cardia, public;
BEGIN;

-- Deterministic pseudo-random number in [0, 1) for a given key.
CREATE FUNCTION pg_temp.u(key text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
    SELECT ('x' || substr(md5(key), 1, 8))::bit(32)::bigint / 4294967296.0
$$;

-- Deterministic standard-normal draw (Box-Muller) for a given key.
CREATE FUNCTION pg_temp.n(key text) RETURNS double precision
LANGUAGE sql IMMUTABLE AS $$
    SELECT sqrt(-2 * ln(greatest(pg_temp.u(key || ':a'), 1e-9))) * cos(2 * pi() * pg_temp.u(key || ':b'))
$$;

-- Deterministic pick from an array.
CREATE FUNCTION pg_temp.pick(arr text[], key text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT arr[1 + floor(pg_temp.u(key) * array_length(arr, 1))::int]
$$;

-- =============================================================================
-- 1. Patient identity
-- =============================================================================

WITH names AS (
    SELECT
        ARRAY['Antonio','José','Manuel','Francisco','David','Juan','Javier','Daniel','José Luis','Carlos',
              'Jesús','Alejandro','Miguel','Rafael','Pedro','Ángel','Pablo','Sergio','Fernando','Jorge',
              'Luis','Alberto','Álvaro','Diego','Adrián','Raúl','Enrique','Ramón','Vicente','Andrés',
              'Joaquín','Santiago','Víctor','Eduardo','Roberto','Jaime','Ignacio','Alfonso','Ricardo','Emilio',
              'Jordi','Marc','Pau','Xavier','Iñaki']                                             AS male,
        ARRAY['María','Carmen','Ana','Isabel','Laura','Pilar','Dolores','Cristina','Marta','Lucía',
              'Elena','Rosa','Francisca','Antonia','Mercedes','Paula','Raquel','Teresa','Sara','Patricia',
              'Rocío','Beatriz','Encarnación','Julia','Silvia','Montserrat','Nuria','Irene','Alicia','Inmaculada',
              'Rosario','Concepción','Sonia','Eva','Andrea','Esther','Victoria','Ángela','Natalia','Margarita',
              'Núria','Laia','Mireia','Ainhoa','Begoña']                                         AS female,
        ARRAY['García','Rodríguez','González','Fernández','López','Martínez','Sánchez','Pérez','Gómez','Martín',
              'Jiménez','Ruiz','Hernández','Díaz','Moreno','Muñoz','Álvarez','Romero','Alonso','Gutiérrez',
              'Navarro','Torres','Domínguez','Vázquez','Ramos','Gil','Ramírez','Serrano','Blanco','Molina',
              'Morales','Suárez','Ortega','Delgado','Castro','Ortiz','Rubio','Marín','Sanz','Núñez',
              'Iglesias','Medina','Garrido','Cortés','Castillo','Santos','Lozano','Guerrero','Cano','Prieto',
              'Méndez','Cruz','Calvo','Gallego','Vidal','León','Márquez','Herrera','Peña','Flores',
              'Cabrera','Campos','Vega','Fuentes','Carrasco','Diez','Caballero','Reyes','Nieto','Aguilar',
              'Puig','Ferrer','Soler','Pujol','Vila','Etxeberria','Costa','Pascual','Santana','Herrero']  AS surname
),
identity AS (
    SELECT p.patient_id,
           pg_temp.pick(CASE p.sex WHEN 'M' THEN n.male ELSE n.female END, p.patient_id || ':first') AS first_name,
           pg_temp.pick(n.surname, p.patient_id || ':s1')                                               AS surname1,
           pg_temp.pick(n.surname, p.patient_id || ':s2')                                               AS surname2
    FROM patient p CROSS JOIN names n
)
UPDATE patient p
SET first_name = coalesce(p.first_name, i.first_name),
    last_name  = coalesce(p.last_name,  i.surname1 || ' ' || i.surname2),
    -- Clearly synthetic health-card id: SYN + zero-padded RANDID (unique because RANDID is).
    cip        = coalesce(p.cip, 'SYN' || lpad(p.patient_id::text, 7, '0')),
    -- Spanish mobile format "6XX XXX XXX".
    phone      = coalesce(p.phone,
                     '6' || lpad(floor(pg_temp.u(p.patient_id || ':ph1') * 100)::int::text, 2, '0') || ' ' ||
                     lpad(floor(pg_temp.u(p.patient_id || ':ph2') * 1000)::int::text, 3, '0') || ' ' ||
                     lpad(floor(pg_temp.u(p.patient_id || ':ph3') * 1000)::int::text, 3, '0')),
    -- example.test is a reserved domain, so these addresses can never deliver.
    email      = coalesce(p.email,
                     lower(translate(replace(i.first_name, ' ', ''), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')) || '.' ||
                     lower(translate(i.surname1,                       'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')) || '.' ||
                     p.patient_id || '@example.test')
FROM identity i
WHERE i.patient_id = p.patient_id
  AND (p.first_name IS NULL OR p.last_name IS NULL OR p.cip IS NULL OR p.phone IS NULL OR p.email IS NULL);

-- =============================================================================
-- 2. Missing indicators: hba1c, serum_creatinine, egfr, acr
--
-- One value per exam, at the exam timestamp, so they line up with the real
-- measurements. Each patient gets a stable personal offset plus a smaller
-- per-exam variation, and values follow the exam's own clinical status:
--   hba1c             diabetic: from the exam's glucose (ADAG: (glucose + 46.7) / 28.7),
--                     at least 6.5; non-diabetic: ~5.3 nudged by glucose and age, below 6.5
--   serum_creatinine  sex baseline, rises with age, hypertension and diabetes
--   egfr              computed from that creatinine with CKD-EPI 2021, so the two agree
--   acr               log-normal around 8 mg/g, higher with diabetes, hypertension
--                     and systolic >= 140
-- =============================================================================

INSERT INTO ingestion_batch (source_kind, source_uri, rows_read)
SELECT 'tabular', 'synthetic://004_synthetic_fill', (SELECT count(*) FROM exam)
WHERE NOT EXISTS (SELECT 1 FROM ingestion_batch WHERE source_uri = 'synthetic://004_synthetic_fill');

CREATE TEMP TABLE synth ON COMMIT DROP AS
WITH base AS (
    SELECT f.patient_id, f.exam_time, f.sex, f.age_years, f.diabetes, f.prev_hypertension,
           f.glucose, f.systolic,
           f.patient_id || ':' || coalesce(f.period, 0) AS ek,     -- per-exam key
           f.patient_id::text                           AS pk      -- per-patient key
    FROM exam_features f
),
lab AS (
    SELECT b.*,
           -- HbA1c (%)
           least(14, greatest(4.0,
               CASE WHEN b.diabetes AND b.glucose IS NOT NULL
                    THEN greatest(6.5, (least(b.glucose, 400) + 46.7) / 28.7 + 0.3)
                    WHEN b.diabetes
                    THEN 7.4
                    -- Non-diabetic: normal range, nudged by glucose and age, capped below 6.5
                    ELSE least(6.4, 5.3 + 0.008 * (coalesce(b.glucose, 80) - 80)
                                        + 0.008 * greatest(b.age_years - 45, 0))
               END
               + 0.25 * pg_temp.n(b.pk || ':a1c') + 0.15 * pg_temp.n(b.ek || ':a1c'))) AS hba1c,
           -- Serum creatinine (mg/dL)
           least(6, greatest(0.4,
               (CASE b.sex WHEN 'M' THEN 0.95 ELSE 0.75 END)
               * (1 + 0.006 * greatest(b.age_years - 40, 0))
               + CASE WHEN b.prev_hypertension THEN 0.08 ELSE 0 END
               + CASE WHEN b.diabetes          THEN 0.12 ELSE 0 END
               + 0.12 * pg_temp.n(b.pk || ':cr') + 0.05 * pg_temp.n(b.ek || ':cr')))   AS creatinine,
           -- Urine albumin-to-creatinine ratio (mg/g)
           least(3000, greatest(1,
               8 * exp(0.6 * pg_temp.n(b.pk || ':acr') + 0.3 * pg_temp.n(b.ek || ':acr'))
               * CASE WHEN b.diabetes                       THEN 2.5 ELSE 1 END
               * CASE WHEN b.prev_hypertension              THEN 1.8 ELSE 1 END
               * CASE WHEN coalesce(b.systolic, 0) >= 140   THEN 1.4 ELSE 1 END))   AS acr
    FROM base b
)
SELECT patient_id, exam_time,
       round(hba1c::numeric, 1)::float8      AS hba1c,
       round(creatinine::numeric, 2)::float8 AS serum_creatinine,
       -- CKD-EPI 2021 (race-free): 142 * min(Scr/k,1)^a * max(Scr/k,1)^-1.200 * 0.9938^age * 1.012 [female]
       round((142
              * power(least(round(creatinine::numeric, 2)::float8 / k, 1), a)
              * power(greatest(round(creatinine::numeric, 2)::float8 / k, 1), -1.200)
              * power(0.9938, age_years)
              * CASE sex WHEN 'F' THEN 1.012 ELSE 1 END)::numeric, 0)::float8 AS egfr,
       round(acr::numeric, 0)::float8        AS acr
FROM lab
CROSS JOIN LATERAL (SELECT CASE sex WHEN 'F' THEN 0.7    ELSE 0.9    END AS k,
                           CASE sex WHEN 'F' THEN -0.241 ELSE -0.302 END AS a) c;

INSERT INTO measurement (patient_id, indicator_code, measured_at, value, source, ingestion_batch_id)
SELECT s.patient_id, v.code, s.exam_time, v.value, 'lab',
       (SELECT batch_id FROM ingestion_batch
        WHERE source_uri = 'synthetic://004_synthetic_fill' ORDER BY started_at DESC LIMIT 1)
FROM synth s
CROSS JOIN LATERAL (VALUES
    ('hba1c',            s.hba1c),
    ('serum_creatinine', s.serum_creatinine),
    ('egfr',             s.egfr),
    ('acr',              s.acr)
) AS v(code, value)
ON CONFLICT (patient_id, indicator_code, measured_at) DO NOTHING;

UPDATE ingestion_batch
SET status = 'succeeded', finished_at = now(),
    rows_loaded = (SELECT count(*) FROM measurement
                   WHERE indicator_code IN ('hba1c', 'serum_creatinine', 'egfr', 'acr'))
WHERE source_uri = 'synthetic://004_synthetic_fill' AND status = 'running';

-- =============================================================================
-- 3. Checks: fail the transaction if anything is off
-- =============================================================================
DO $$
BEGIN
    ASSERT NOT EXISTS (SELECT 1 FROM patient
                       WHERE first_name IS NULL OR last_name IS NULL OR cip IS NULL
                          OR phone IS NULL OR email IS NULL),
           'patient: some identity fields are still empty';
    ASSERT (SELECT count(*) FROM measurement
            WHERE indicator_code IN ('hba1c', 'serum_creatinine', 'egfr', 'acr'))
           = 4 * (SELECT count(*) FROM exam),
           'measurement: expected 4 synthetic values per exam';
    ASSERT NOT EXISTS (SELECT 1 FROM measurement WHERE indicator_code = 'hba1c' AND value NOT BETWEEN 4 AND 14),
           'hba1c out of range';
    ASSERT NOT EXISTS (SELECT 1 FROM measurement WHERE indicator_code = 'egfr' AND value NOT BETWEEN 5 AND 150),
           'egfr out of range';
    RAISE NOTICE 'ok - synthetic fill complete';
END $$;

COMMIT;
