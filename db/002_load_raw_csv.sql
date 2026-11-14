-- =============================================================================
-- Cardia · Load data/raw.csv (Framingham longitudinal teaching dataset)
--
-- Usage (from the repository root):
--   psql -d cardia -v ON_ERROR_STOP=1 -v baseline=2013-01-01 -f db/002_load_raw_csv.sql
--
-- `baseline` is the calendar date assigned to day 0 (TIME = 0) of every patient.
-- raw.csv has no calendar dates, only days since the baseline exam.
-- =============================================================================

SET search_path = cardia, public;
BEGIN;

CREATE TEMP TABLE raw_stage (
    randid bigint, sex smallint, totchol numeric, age smallint, sysbp numeric, diabp numeric,
    cursmoke smallint, cigpday smallint, bmi numeric, diabetes smallint, bpmeds smallint,
    heartrte numeric, glucose numeric, educ smallint,
    prevchd smallint, prevap smallint, prevmi smallint, prevstrk smallint, prevhyp smallint,
    "time" integer, period smallint, hdlc numeric, ldlc numeric,
    death smallint, angina smallint, hospmi smallint, mi_fchd smallint, anychd smallint,
    stroke smallint, cvd smallint, hyperten smallint,
    timeap integer, timemi integer, timemifc integer, timechd integer,
    timestrk integer, timecvd integer, timedth integer, timehyp integer
) ON COMMIT DROP;

\copy raw_stage FROM 'data/raw.csv' WITH (FORMAT csv, HEADER true, NULL '')

INSERT INTO ingestion_batch (source_kind, source_uri, rows_read)
SELECT 'tabular', 's3://cardia-raw/tabular/framingham/raw.csv', count(*) FROM raw_stage;

-- A. Static: one row per patient. Every patient has a PERIOD = 1 row.
INSERT INTO patient (patient_id, sex, education_level, birth_year, baseline_date)
SELECT randid,
       CASE sex WHEN 1 THEN 'M' ELSE 'F' END,
       educ,
       extract(year FROM :'baseline'::date)::int - age,
       :'baseline'::date
FROM raw_stage
WHERE period = 1;

INSERT INTO patient_outcome
SELECT DISTINCT randid,
       death = 1, angina = 1, hospmi = 1, mi_fchd = 1, anychd = 1, stroke = 1, cvd = 1, hyperten = 1,
       timedth, timeap, timemi, timemifc, timechd, timestrk, timecvd, timehyp
FROM raw_stage;

-- B. Time series: one exam row per visit ...
INSERT INTO exam (patient_id, exam_time, period, days_since_baseline, age_years,
                  current_smoker, cigs_per_day, bp_meds, diabetes,
                  prev_chd, prev_angina, prev_mi, prev_stroke, prev_hypertension,
                  ingestion_batch_id)
SELECT randid, (:'baseline'::date + "time")::timestamp AT TIME ZONE 'UTC', period, "time", age,
       cursmoke = 1, cigpday, bpmeds = 1, diabetes = 1,
       prevchd = 1, prevap = 1, prevmi = 1, prevstrk = 1, prevhyp = 1,
       (SELECT batch_id FROM ingestion_batch ORDER BY started_at DESC LIMIT 1)
FROM raw_stage;

-- ... and one measurement row per non-missing numeric value.
INSERT INTO measurement (patient_id, indicator_code, measured_at, value, source, ingestion_batch_id)
SELECT s.randid, v.code, (:'baseline'::date + s."time")::timestamp AT TIME ZONE 'UTC', v.value, 'exam',
       (SELECT batch_id FROM ingestion_batch ORDER BY started_at DESC LIMIT 1)
FROM raw_stage s
CROSS JOIN LATERAL (VALUES
    ('systolic',          s.sysbp),
    ('diastolic',         s.diabp),
    ('heart_rate',        s.heartrte),
    ('bmi',               s.bmi),
    ('total_cholesterol', s.totchol),
    ('hdl_cholesterol',   s.hdlc),
    ('ldl',               s.ldlc),
    ('glucose',           s.glucose)
) AS v(code, value)
WHERE v.value IS NOT NULL;

-- Timeline entry for each exam.
INSERT INTO clinical_event (patient_id, event_time, event_type, title)
SELECT patient_id, exam_time, 'exam', 'Examen ' || period FROM exam;

UPDATE ingestion_batch
SET status = 'succeeded', finished_at = now(),
    rows_loaded = (SELECT count(*) FROM exam)
WHERE status = 'running';

COMMIT;
