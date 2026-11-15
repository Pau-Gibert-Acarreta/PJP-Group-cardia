# Cardia data layer

Schema for block 2 of the architecture ("Capa de Datos"): PostgreSQL + TimescaleDB + pgvector, plus the object storage layout for raw files.

| File | Purpose |
| --- | --- |
| `001_schema.sql` | Tables, hypertables, HNSW index and read views. |
| `005_knn.sql` | Vector of 20 dimensions and `embedding_model` for the KNN of similar patients. |
| `003_smoke_test.sql` | Checks the load, hypertables, pgvector, constraints and views; rolls back. |

The data is no longer loaded with SQL scripts: an ETL in `backend/` builds separate sources from `raw.csv` and loads them (the old `002_load_raw_csv.sql` and `004_synthetic_fill.sql` were retired; the ETL reproduces exactly the database they produced).

```sh
# From backend/ (data/raw.csv must exist; it is not in git)
uv run python -m app.jobs.build_sources          # once: raw.csv + synthetic data -> data/sources/*.csv
uv run python -m app.jobs.load_sources --reset   # empties the database, recreates 001 + 005 and loads the sources
uv run python -m app.jobs.evaluate_findings      # rule engine
uv run python -m app.jobs.build_knn_index        # similar patients
uv run python -m app.jobs.generate_lab_reports --all && uv run python -m app.jobs.ingest_lab_reports   # PDFs (~15 min)

# From the repository root
docker exec cardia-db psql -U postgres -d cardia -v ON_ERROR_STOP=1 -f db/003_smoke_test.sql
```

## Data sources (`data/sources/`, built by `app/etl/sources.py`)

`raw.csv` is the Framingham longitudinal dataset: 11,627 rows, 4,434 patients, 1 to 3 exams each (`RANDID` × `PERIOD`). It is split by the system each value would come from in a real centre, and the synthetic data is generated there. The sources keep the study codes (sex 1/2, flags 0/1) and the study day (`TIME`); the ETL does the transformations. Neither `raw.csv` nor the sources are in git.

| Source | Simulated system | Shape | Content |
| --- | --- | --- | --- |
| `ehr_patients.csv` | Health record | one row per patient | `SEX`, `educ` + synthetic identity: name, CIP (`SYN` + RANDID), phone, email (`@example.test`) |
| `ehr_visits.csv` | Health record | one row per visit | `PERIOD`, `TIME`, `AGE`, `CURSMOKE`, `CIGPDAY`, `BPMEDS`, `DIABETES`, `PREVCHD`, `PREVAP`, `PREVMI`, `PREVSTRK`, `PREVHYP` |
| `data_pressure.csv` | Vital signs monitor | wide, one row per reading | `SYSBP`, `DIABP`, `HEARTRTE`, `BMI` |
| `data_blood.csv` | Laboratory (LIS), blood | long, one row per result, LOINC | `GLUCOSE` (2345-7), `TOTCHOL` (2093-3), `HDLC` (2085-9), `LDLC` (13457-7) + synthetic HbA1c (4548-4) and creatinine (2160-0) |
| `data_urine.csv` | Laboratory (LIS), urine | long, LOINC | synthetic albumin/creatinine ratio (9318-7) |
| `registry_outcomes.csv` | Follow-up registry | one row per patient | `DEATH` … `TIMEHYP` (24-year outcomes, training labels only) |

Synthetic values (deterministic, from `md5(patient_id + key)`):

- HbA1c: diabetic, from the visit's glucose (ADAG), at least 6.5 %; otherwise about 5.3 %, nudged by glucose and age.
- Creatinine: sex baseline, rising with age, hypertension and diabetes.
- ACR: log-normal around 8 mg/g, higher with diabetes, hypertension and systolic ≥ 140.
- The phone numbers are random and could belong to real people, so never call or text them from the app.

## ETL (`app/etl/load.py`)

| Transformation | Detail |
| --- | --- |
| Dates | `baseline_date + study day` at UTC midnight (`--baseline`, default 2013-01-01; `TIME` reaches 4,854 days, so a later baseline puts exams in the future). |
| Patient | sex 1/2 → M/F; `birth_year` = baseline year − age at the first visit. |
| Flags | 0/1 → boolean; empty → NULL. |
| Measurements | one row per present value, missing values are not stored; vitals `source = 'exam'`, laboratory `source = 'lab'`. |
| Name normalisation | LOINC → `indicator.code`, checking the unit; an unknown code or unit aborts the load. |
| Derived | eGFR from creatinine, age and sex with CKD-EPI 2021. |
| Timeline | one `clinical_event` per test and day, not per visit: blood analysis (`test_kind = 'blood'`), urine test (`urine`) and vital signs (`vitals`). Groups defined in `backend/app/clinical_tests.py`. |
| Traceability | one `ingestion_batch` per source; every exam and measurement points to its batch. |

The whole load runs in one transaction: any inconsistency leaves the database empty rather than half loaded.

## What the frontend reads

| Frontend field | Source |
| --- | --- |
| `patient.measurements[field] = [{ value, date, unit }]` | `measurement` joined to `indicator`; `indicator.code` is the `field` key. |
| `id`, `sex`, `age`, `lastTest`, `followup`, `cip`, `firstName`, `lastName` | `patient_overview` view. |
| `conditions` | Flags of the latest exam in `patient_overview` (`prev_hypertension`, `diabetes`, `current_smoker`, ...). |
| `risk`, `history.risk` | `risk_prediction` where `target = 'cv'` (latest row, full series). |
| `factors` | `risk_prediction.shap_top_k`. |
| `riskOverride` | `risk_classification_override` where `cleared_at IS NULL`. |
| `events` | `clinical_event`, with `document_id` pointing to the PDF or ECG. |
| `notes` | `clinical_note`. |
| Findings | `finding` (written by the rule engine). |
| Similar patients (KNN) | `exam_embedding`. |

## Embedding (`exam_embedding.embedding`, `vector(20)`)

`005_knn.sql` sets the dimension to 20 and adds `embedding_model` (features, weights and scaler per version). The vectors are built by `backend/` (`uv run python -m app.jobs.build_knn_index`), version `knn-v1`: one vector per historical exam, so each indexed case has a known outcome.

Each component is the z-score of a feature times `sqrt(weight)`, so pgvector's L2 distance is a weighted Euclidean distance. A missing value is stored as 0 (the mean). Features, in order (definition and weights in `backend/app/knn/features.py`):

- Context: `age_years`, `sex`, `current_smoker`, `cigs_per_day`, `diabetes`, `bp_meds`, `prev_hypertension`, `prev_chd`, `prev_stroke`.
- Values at the exam: `bmi`, `systolic`, `diastolic`, `heart_rate`, `total_cholesterol`, `hdl_cholesterol`, `glucose`.
- Trends (change per year since the previous measurement): `systolic_trend`, `total_cholesterol_trend`, `bmi_trend`, `glucose_trend`.

Only original Framingham variables are used: the synthetic labs (HbA1c, creatinine, eGFR, ACR) are left out.

Changing features or weights means rebuilding the index; changing the number of features means changing the column dimension too.

## Object storage

Two buckets. The database holds one `document` row per object; nothing reads the bucket by listing it.

```
cardia-raw/                         immutable, versioned, written only by the ETL
  tabular/{source}/{batch_id}/{filename}                    raw.csv and other bulk extracts
  timeseries/{source}/{batch_id}/{filename}                 device or lab feeds as received
  documents/{patient_id}/{kind}/{document_id}.{ext}         PDFs, reports, ECGs, images

cardia-derived/                     reproducible from cardia-raw, safe to delete
  ocr/{document_id}/text.txt                                 extracted text
  ocr/{document_id}/extraction.json                          structured values parsed from the document
  previews/{document_id}/page-{n}.png                        page images for the UI
```

| Key part | Value |
| --- | --- |
| `source` | Origin system, for example `framingham`. |
| `batch_id` | `ingestion_batch.batch_id`. |
| `patient_id` | `patient.patient_id`. |
| `kind` | `lab_report`, `clinical_report`, `ecg`, `imaging`, `other` (same list as `document.kind`). |
| `document_id` | `document.document_id`, generated before upload. |

Rules:

- Keys carry ids only. No names, health-card numbers or original filenames; the original filename goes in `document.original_filename`.
- Objects in `cardia-raw` are never overwritten. A corrected file is a new `document_id`.
- `document.sha256` is unique, so uploading the same file twice is rejected at the metadata insert.
- Object metadata repeats `document-id`, `patient-id`, `kind`, `sha256` and `batch-id`, so the bucket can be reconciled against the database.
- The backend serves a file by looking up `document_id`, then issuing a short-lived presigned URL. Bucket and key are not sent to the frontend.

Current setup (MVP without S3): lab report PDFs are stored with `storage_backend = 'postgres'` and the bytes in `document_blob` (generated and ingested by `backend/`, see its README). Bucket and key are still filled in with the values above, so the later move to S3 is a copy plus an update of `storage_backend`.
