-- =============================================================================
-- Cardia · Data layer schema
-- PostgreSQL 16 + TimescaleDB 2.x + pgvector >= 0.5
--
-- Layout
--   A. Static tabular data        patient, patient_outcome
--   B. Time series (hypertables)  exam, measurement, risk_prediction
--   C. Vectors (pgvector / HNSW)  exam_embedding
--   D. Documents (object storage) ingestion_batch, document, document_blob
--   E. Application state          clinical_event, finding, clinical_note,
--                                 patient_followup, risk_classification_override
--   F. Read views for the API     latest_measurement, latest_risk_prediction,
--                                 exam_features, patient_overview
--
-- Conventions
--   * patient_id is RANDID from the raw source.
--   * A missing value is an absent row, never NULL/0 (frontend data contract).
--   * Every time-series row carries an absolute timestamp. The raw source only
--     has "days since baseline", so the ETL anchors it on patient.baseline_date.
--   * Nothing has a foreign key INTO a hypertable (not supported before
--     TimescaleDB 2.16); references to exams are (patient_id, exam_time) pairs.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS cardia;
SET search_path = cardia, public;

-- =============================================================================
-- A. STATIC TABULAR DATA  (one row per patient, values that never change)
-- =============================================================================

CREATE TABLE patient (
    patient_id       bigint      PRIMARY KEY,                 -- RANDID
    sex              char(1)     NOT NULL CHECK (sex IN ('M', 'F')),   -- SEX 1=M, 2=F
    education_level  smallint    CHECK (education_level BETWEEN 1 AND 4), -- educ; NULL = unknown
    birth_year       smallint    NOT NULL,                    -- derived: year(baseline) - AGE at PERIOD 1
    baseline_date    date        NOT NULL,                    -- day 0 of TIME; anchor for every timestamp

    -- Identity shown in the UI header. NULL for the anonymised Framingham load.
    first_name       text,
    last_name        text,
    cip              text        UNIQUE,                      -- health-card id
    phone            text,
    email            text,

    source_system    text        NOT NULL DEFAULT 'framingham',
    created_at       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN patient.education_level IS
    '1 = 0-11 years, 2 = high school / GED, 3 = some college / vocational, 4 = college degree or more';
COMMENT ON COLUMN patient.birth_year IS
    'Age is never stored as a patient attribute: derive it from birth_year. exam.age_years keeps the age recorded at each exam.';

-- Adjudicated 24-year follow-up. Constant per patient, but these are OUTCOMES:
-- they describe the future relative to every exam. Training labels only.
-- Never join them into serving features and never expose them through the API.
CREATE TABLE patient_outcome (
    patient_id        bigint   PRIMARY KEY REFERENCES patient ON DELETE CASCADE,

    death             boolean  NOT NULL,   -- DEATH    death from any cause
    angina            boolean  NOT NULL,   -- ANGINA   angina pectoris
    hosp_mi           boolean  NOT NULL,   -- HOSPMI   hospitalised myocardial infarction
    mi_fchd           boolean  NOT NULL,   -- MI_FCHD  hospitalised MI or fatal CHD
    any_chd           boolean  NOT NULL,   -- ANYCHD   angina, MI, coronary insufficiency or fatal CHD
    stroke            boolean  NOT NULL,   -- STROKE   any stroke, fatal or not
    cvd               boolean  NOT NULL,   -- CVD      MI, fatal CHD or stroke
    hypertension      boolean  NOT NULL,   -- HYPERTEN incident hypertension

    -- Days from baseline to the first event, or to censoring when the flag is false.
    days_to_death         integer NOT NULL CHECK (days_to_death        >= 0),  -- TIMEDTH
    days_to_angina        integer NOT NULL CHECK (days_to_angina       >= 0),  -- TIMEAP
    days_to_hosp_mi       integer NOT NULL CHECK (days_to_hosp_mi      >= 0),  -- TIMEMI
    days_to_mi_fchd       integer NOT NULL CHECK (days_to_mi_fchd      >= 0),  -- TIMEMIFC
    days_to_any_chd       integer NOT NULL CHECK (days_to_any_chd      >= 0),  -- TIMECHD
    days_to_stroke        integer NOT NULL CHECK (days_to_stroke       >= 0),  -- TIMESTRK
    days_to_cvd           integer NOT NULL CHECK (days_to_cvd          >= 0),  -- TIMECVD
    days_to_hypertension  integer NOT NULL CHECK (days_to_hypertension >= 0)   -- TIMEHYP
);

COMMENT ON TABLE patient_outcome IS
    'ML labels (future events). Read by 4A training only; using them at serving time is target leakage.';

-- =============================================================================
-- B. TIME SERIES
-- =============================================================================

-- Indicator catalogue. `code` is exactly the `field` key the frontend uses in
-- src/config/indicators.json, finding-rules.json and patient.measurements.
CREATE TABLE indicator (
    code        text     PRIMARY KEY,
    label       text     NOT NULL,
    unit        text     NOT NULL,          -- single canonical unit; the ETL converts before insert
    kind        text     NOT NULL CHECK (kind IN ('vital', 'lab')),
    decimals    smallint NOT NULL DEFAULT 0,
    raw_column  text                         -- column in raw.csv; NULL = not present in that source
);

INSERT INTO indicator (code, label, unit, kind, decimals, raw_column) VALUES
    ('systolic',          'PA sistólica',       'mmHg',            'vital', 0, 'SYSBP'),
    ('diastolic',         'PA diastólica',      'mmHg',            'vital', 0, 'DIABP'),
    ('heart_rate',        'Frecuencia cardíaca','lpm',             'vital', 0, 'HEARTRTE'),
    ('bmi',               'IMC',                'kg/m²',           'vital', 1, 'BMI'),
    ('total_cholesterol', 'Colesterol total',   'mg/dL',           'lab',   0, 'TOTCHOL'),
    ('hdl_cholesterol',   'Colesterol HDL',     'mg/dL',           'lab',   0, 'HDLC'),
    ('ldl',               'Colesterol LDL',     'mg/dL',           'lab',   0, 'LDLC'),
    ('glucose',           'Glucosa',            'mg/dL',           'lab',   0, 'GLUCOSE'),
    -- Used by the frontend (overview table, KDIGO, rules) but absent from raw.csv:
    ('hba1c',             'HbA1c',              '%',               'lab',   1, NULL),
    ('acr',               'Albuminuria (ACR)',  'mg/g',            'lab',   0, NULL),
    ('serum_creatinine',  'Creatinina sérica',  'mg/dL',           'lab',   2, NULL),
    ('egfr',              'eGFR',               'mL/min/1,73 m²',  'lab',   0, NULL);

-- One row per patient visit: the clinical status and questionnaire answers that
-- change between visits (RANDID x PERIOD in raw.csv).
CREATE TABLE exam (
    patient_id           bigint      NOT NULL REFERENCES patient ON DELETE CASCADE,
    exam_time            timestamptz NOT NULL,              -- baseline_date + TIME days
    period               smallint    CHECK (period BETWEEN 1 AND 3),  -- PERIOD; NULL for non-study visits
    days_since_baseline  integer     NOT NULL CHECK (days_since_baseline >= 0),  -- TIME
    age_years            smallint    NOT NULL,              -- AGE

    current_smoker       boolean     NOT NULL,              -- CURSMOKE
    cigs_per_day         smallint    CHECK (cigs_per_day >= 0),  -- CIGPDAY (NULL = not reported)
    bp_meds              boolean,                           -- BPMEDS  (NULL = not reported)
    diabetes             boolean     NOT NULL,              -- DIABETES
    prev_chd             boolean     NOT NULL,              -- PREVCHD
    prev_angina          boolean     NOT NULL,              -- PREVAP
    prev_mi              boolean     NOT NULL,              -- PREVMI
    prev_stroke          boolean     NOT NULL,              -- PREVSTRK
    prev_hypertension    boolean     NOT NULL,              -- PREVHYP

    ingestion_batch_id   uuid,
    PRIMARY KEY (patient_id, exam_time)
);
SELECT create_hypertable('cardia.exam', 'exam_time', chunk_time_interval => INTERVAL '1 year');
CREATE INDEX exam_time_idx ON exam (exam_time DESC);

-- Narrow numeric series: one row per (patient, indicator, instant). Maps 1:1 to
-- the frontend contract  measurements[field] = [{ value, date, unit }].
-- Adding an indicator is an INSERT into `indicator`, not a migration.
CREATE TABLE measurement (
    patient_id          bigint           NOT NULL REFERENCES patient ON DELETE CASCADE,
    indicator_code      text             NOT NULL REFERENCES indicator,
    measured_at         timestamptz      NOT NULL,
    value               double precision NOT NULL,          -- already in indicator.unit
    source              text             NOT NULL DEFAULT 'exam'
                                         CHECK (source IN ('exam', 'lab', 'document', 'manual')),
    document_id         uuid,                               -- document it was extracted from, if any
    ingestion_batch_id  uuid,
    ingested_at         timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (patient_id, indicator_code, measured_at)
);
SELECT create_hypertable('cardia.measurement', 'measured_at', chunk_time_interval => INTERVAL '1 year');
CREATE INDEX measurement_indicator_time_idx ON measurement (indicator_code, measured_at DESC);

-- Output of 4B "Motor Riesgo + XAI". Append-only, so it is also the risk history
-- the patient chart draws.
CREATE TABLE risk_prediction (
    patient_id       bigint           NOT NULL REFERENCES patient ON DELETE CASCADE,
    target           text             NOT NULL CHECK (target IN ('cv', 'diabetes', 'renal')),
    predicted_at     timestamptz      NOT NULL,
    model_name       text             NOT NULL,
    model_version    text             NOT NULL,              -- Champion version in the model registry
    probability      double precision NOT NULL CHECK (probability BETWEEN 0 AND 1),
    horizon_years    smallint         NOT NULL,
    input_exam_time  timestamptz      NOT NULL,              -- exam the features were taken from
    trigger          text             NOT NULL DEFAULT 'new_test'
                                      CHECK (trigger IN ('new_test', 'backfill', 'model_promotion', 'manual')),
    features         jsonb            NOT NULL,              -- exact feature vector scored (audit / reproducibility)
    shap_base_value  double precision,
    -- Local SHAP, top-K by |contribution|, ordered:
    -- [{ "feature": "systolic", "label": "PA sistólica", "value": 148, "unit": "mmHg", "contribution": 0.041 }, ...]
    shap_top_k       jsonb            NOT NULL DEFAULT '[]',
    PRIMARY KEY (patient_id, target, predicted_at, model_version)
);
SELECT create_hypertable('cardia.risk_prediction', 'predicted_at', chunk_time_interval => INTERVAL '1 year');

-- =============================================================================
-- C. VECTORS  (4B "KNN on-the-fly": similar patients at their previous exam)
-- =============================================================================

-- One vector per exam, not per patient: the KNN looks for patients whose state
-- at some past exam resembles this patient now, then reads what happened next.
-- Plain table on purpose: an HNSW index on a hypertable is built per chunk and
-- would not give one global nearest-neighbour graph.
CREATE TABLE exam_embedding (
    patient_id         bigint      NOT NULL REFERENCES patient ON DELETE CASCADE,
    exam_time          timestamptz NOT NULL,
    embedding_version  text        NOT NULL,     -- feature set + scaler version
    embedding          vector(16)  NOT NULL,     -- standardised clinical feature vector, see db/README.md
    created_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (patient_id, exam_time, embedding_version)
);
CREATE INDEX exam_embedding_hnsw_idx ON exam_embedding
    USING hnsw (embedding vector_l2_ops) WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- D. DOCUMENTS  (metadata here, bytes in object storage)
-- =============================================================================

CREATE TABLE ingestion_batch (
    batch_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_kind    text        NOT NULL CHECK (source_kind IN ('tabular', 'timeseries', 'document')),
    source_uri     text        NOT NULL,          -- raw file as landed in object storage
    status         text        NOT NULL DEFAULT 'running'
                               CHECK (status IN ('running', 'succeeded', 'failed')),
    rows_read      integer,
    rows_loaded    integer,
    error          text,
    started_at     timestamptz NOT NULL DEFAULT now(),
    finished_at    timestamptz
);

CREATE TABLE document (
    document_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id         bigint      REFERENCES patient ON DELETE CASCADE,   -- NULL for bulk files (raw.csv)
    kind               text        NOT NULL CHECK (kind IN
                           ('lab_report', 'clinical_report', 'ecg', 'imaging', 'tabular_extract', 'other')),
    storage_backend    text        NOT NULL DEFAULT 's3' CHECK (storage_backend IN ('s3', 'postgres')),
    bucket             text        NOT NULL,
    object_key         text        NOT NULL,
    content_type       text        NOT NULL,       -- application/pdf, image/png, text/csv ...
    size_bytes         bigint      NOT NULL CHECK (size_bytes >= 0),
    sha256             char(64)    NOT NULL,       -- integrity + de-duplication
    original_filename  text,
    document_date      date,                       -- clinical date of the document, not the upload date
    ocr_status         text        NOT NULL DEFAULT 'not_applicable'
                                   CHECK (ocr_status IN ('not_applicable', 'pending', 'done', 'failed')),
    ocr_text_key       text,                       -- object key of the extracted text (derived bucket)
    extracted          jsonb,                      -- structured values parsed from the document
    ingestion_batch_id uuid        REFERENCES ingestion_batch,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (bucket, object_key),
    UNIQUE (sha256)
);
CREATE INDEX document_patient_idx ON document (patient_id, document_date DESC);

-- MVP fallback ("Mismo PostgreSQL" in the diagram): same metadata row with
-- storage_backend = 'postgres' and the bytes here. Moving to S3 later is a copy
-- plus an UPDATE of storage_backend; keys and document_id do not change.
CREATE TABLE document_blob (
    document_id  uuid  PRIMARY KEY REFERENCES document ON DELETE CASCADE,
    content      bytea NOT NULL
);

-- =============================================================================
-- E. APPLICATION STATE  (written by the Core Backend on behalf of the clinician)
-- =============================================================================

-- Patient timeline in the detail view (tests, diagnoses, treatment reviews, ECGs).
CREATE TABLE clinical_event (
    event_id     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   bigint      NOT NULL REFERENCES patient ON DELETE CASCADE,
    event_time   timestamptz NOT NULL,
    event_type   text        NOT NULL CHECK (event_type IN
                     ('exam', 'laboratory', 'exploration', 'treatment', 'history')),
    title        text        NOT NULL,
    description  text,
    document_id  uuid        REFERENCES document ON DELETE SET NULL
);
CREATE INDEX clinical_event_patient_idx ON clinical_event (patient_id, event_time DESC);

-- Findings raised by the rule engine (rules.json) when a new test arrives.
CREATE TABLE finding (
    finding_id      uuid             PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      bigint           NOT NULL REFERENCES patient ON DELETE CASCADE,
    rule_id         text             NOT NULL,          -- id in finding-rules.json
    rules_version   text             NOT NULL,
    indicator_code  text             NOT NULL REFERENCES indicator,
    severity        text             NOT NULL CHECK (severity IN ('attention', 'warning')),
    title           text             NOT NULL,
    current_value   double precision NOT NULL,
    current_at      timestamptz      NOT NULL,
    previous_value  double precision NOT NULL,
    previous_at     timestamptz      NOT NULL,
    detected_at     timestamptz      NOT NULL DEFAULT now(),
    resolved_at     timestamptz                          -- NULL = active
);
CREATE UNIQUE INDEX finding_active_uq ON finding (patient_id, rule_id) WHERE resolved_at IS NULL;

CREATE TABLE clinical_note (
    note_id     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  bigint      NOT NULL REFERENCES patient ON DELETE CASCADE,
    text        text        NOT NULL CHECK (length(btrim(text)) > 0),
    author      text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX clinical_note_patient_idx ON clinical_note (patient_id, updated_at DESC);

CREATE TABLE patient_followup (
    patient_id  bigint      PRIMARY KEY REFERENCES patient ON DELETE CASCADE,
    followup    boolean     NOT NULL,
    updated_by  text        NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- The clinician may change the risk LEVEL, never the model probability.
-- Rows are never updated except to set cleared_at, so this is the audit trail.
CREATE TABLE risk_classification_override (
    override_id  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id   bigint      NOT NULL REFERENCES patient ON DELETE CASCADE,
    level        text        NOT NULL CHECK (level       IN ('high', 'medium', 'low')),
    model_level  text        NOT NULL CHECK (model_level IN ('high', 'medium', 'low')),
    reason       text        NOT NULL CHECK (length(btrim(reason)) > 0),
    author       text        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    cleared_at   timestamptz,                             -- NULL = in force
    CHECK (level <> model_level)
);
CREATE UNIQUE INDEX risk_override_active_uq ON risk_classification_override (patient_id)
    WHERE cleared_at IS NULL;

-- =============================================================================
-- F. READ VIEWS FOR THE CORE BACKEND
-- =============================================================================

-- Last value of every indicator per patient (key indicators, KDIGO).
CREATE VIEW latest_measurement AS
SELECT DISTINCT ON (patient_id, indicator_code)
       patient_id, indicator_code, measured_at, value
FROM measurement
ORDER BY patient_id, indicator_code, measured_at DESC;

-- Last stored prediction per patient and target ("Vista General usa predicciones ya guardadas").
CREATE VIEW latest_risk_prediction AS
SELECT DISTINCT ON (patient_id, target) *
FROM risk_prediction
ORDER BY patient_id, target, predicted_at DESC;

-- Wide, one row per exam: model features for training (4A), serving (4B) and embeddings.
CREATE VIEW exam_features AS
SELECT e.patient_id, e.exam_time, e.period, e.days_since_baseline,
       p.sex, p.education_level, e.age_years,
       e.current_smoker, e.cigs_per_day, e.bp_meds, e.diabetes,
       e.prev_chd, e.prev_angina, e.prev_mi, e.prev_stroke, e.prev_hypertension,
       m.systolic, m.diastolic, m.heart_rate, m.bmi,
       m.total_cholesterol, m.hdl_cholesterol, m.ldl, m.glucose
FROM exam e
JOIN patient p USING (patient_id)
LEFT JOIN LATERAL (
    SELECT max(value) FILTER (WHERE indicator_code = 'systolic')          AS systolic,
           max(value) FILTER (WHERE indicator_code = 'diastolic')         AS diastolic,
           max(value) FILTER (WHERE indicator_code = 'heart_rate')        AS heart_rate,
           max(value) FILTER (WHERE indicator_code = 'bmi')               AS bmi,
           max(value) FILTER (WHERE indicator_code = 'total_cholesterol') AS total_cholesterol,
           max(value) FILTER (WHERE indicator_code = 'hdl_cholesterol')   AS hdl_cholesterol,
           max(value) FILTER (WHERE indicator_code = 'ldl')               AS ldl,
           max(value) FILTER (WHERE indicator_code = 'glucose')           AS glucose
    FROM measurement
    WHERE patient_id = e.patient_id AND measured_at = e.exam_time
) m ON true;

-- One row per patient for the list view (search, filters, sort, CSV export).
CREATE VIEW patient_overview AS
SELECT p.patient_id, p.first_name, p.last_name, p.cip, p.sex,
       le.age_years                   AS age,
       le.exam_time                   AS last_test,
       le.current_smoker, le.diabetes, le.bp_meds,
       le.prev_hypertension, le.prev_chd, le.prev_stroke,
       rp.probability                 AS cv_risk,
       rp.predicted_at                AS cv_risk_at,
       rp.model_version               AS cv_risk_model_version,
       ro.level                       AS risk_override_level,
       ro.reason                      AS risk_override_reason,
       coalesce(pf.followup, false)   AS followup,
       (SELECT count(*) FROM finding f
         WHERE f.patient_id = p.patient_id AND f.resolved_at IS NULL) AS active_findings
FROM patient p
LEFT JOIN LATERAL (
    SELECT * FROM exam e WHERE e.patient_id = p.patient_id
    ORDER BY e.exam_time DESC LIMIT 1
) le ON true
LEFT JOIN latest_risk_prediction rp
       ON rp.patient_id = p.patient_id AND rp.target = 'cv'
LEFT JOIN risk_classification_override ro
       ON ro.patient_id = p.patient_id AND ro.cleared_at IS NULL
LEFT JOIN patient_followup pf
       ON pf.patient_id = p.patient_id;
