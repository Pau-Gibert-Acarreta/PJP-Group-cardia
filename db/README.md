# Cardia data layer

Schema for block 2 of the architecture ("Capa de Datos"): PostgreSQL + TimescaleDB + pgvector, plus the object storage layout for raw files.

| File | Purpose |
| --- | --- |
| `001_schema.sql` | Tables, hypertables, HNSW index and read views. |
| `002_load_raw_csv.sql` | Loads `data/raw.csv` into the schema. |
| `004_synthetic_fill.sql` | Fills the fields the frontend needs but `raw.csv` lacks with fake data (see below). Optional. |
| `005_knn.sql` | Vector of 20 dimensions and `embedding_model` for the KNN of similar patients. |
| `003_smoke_test.sql` | Checks the load, hypertables, pgvector, constraints and views; rolls back. |

```sh
createdb cardia
psql -d cardia -v ON_ERROR_STOP=1 -f db/001_schema.sql
psql -d cardia -v ON_ERROR_STOP=1 -v baseline=2013-01-01 -f db/002_load_raw_csv.sql
psql -d cardia -v ON_ERROR_STOP=1 -f db/004_synthetic_fill.sql   # optional, demo data
psql -d cardia -v ON_ERROR_STOP=1 -f db/005_knn.sql
psql -d cardia -v ON_ERROR_STOP=1 -f db/003_smoke_test.sql
```

## Where each raw.csv column goes

`raw.csv` is the Framingham longitudinal dataset: 11,627 rows, 4,434 patients, 1 to 3 exams each (`RANDID` × `PERIOD`).

`data/raw.csv` is not in git (see `.gitignore`). Copy it into `data/` locally before running the loader.

| Destination | Raw columns | Why |
| --- | --- | --- |
| `patient` (static) | `RANDID`, `SEX`, `educ` | Identical on every row of a patient. |
| `patient` (derived) | `AGE` at period 1 → `birth_year` | Age changes between exams, birth year does not. |
| `patient_outcome` (static, labels) | `DEATH`, `ANGINA`, `HOSPMI`, `MI_FCHD`, `ANYCHD`, `STROKE`, `CVD`, `HYPERTEN`, `TIMEDTH`, `TIMEAP`, `TIMEMI`, `TIMEMIFC`, `TIMECHD`, `TIMESTRK`, `TIMECVD`, `TIMEHYP` | Constant per patient, but they describe the 24-year follow-up. Training labels only. |
| `exam` (hypertable) | `TIME`, `PERIOD`, `AGE`, `CURSMOKE`, `CIGPDAY`, `BPMEDS`, `DIABETES`, `PREVCHD`, `PREVAP`, `PREVMI`, `PREVSTRK`, `PREVHYP` | Status and questionnaire answers that change between exams. |
| `measurement` (hypertable) | `SYSBP`, `DIABP`, `HEARTRTE`, `BMI`, `TOTCHOL`, `HDLC`, `LDLC`, `GLUCOSE` | Numeric series, one row per value. Missing values are not stored. |

Timestamps are `patient.baseline_date + TIME days`. The source has no calendar dates, so `baseline_date` is set by the loader (`-v baseline=...`). Use 2013-01-01: `TIME` reaches 4,854 days, so a later baseline puts some exams in the future.

## Synthetic data (`004_synthetic_fill.sql`)

`raw.csv` is anonymised and has no kidney or HbA1c labs, but the frontend shows them. This script fills only those gaps, with **fake** values:

| Target | Fields | How |
| --- | --- | --- |
| `patient` | `first_name`, `last_name` | Spanish first name matching `sex`, two surnames. |
| `patient` | `cip` | `SYN` + zero-padded `RANDID` (for example `SYN0002448`), so it is unique and obviously fake. |
| `patient` | `phone`, `email` | `6XX XXX XXX`; `name.surname.RANDID@example.test` (reserved domain, never delivers). |
| `measurement` | `hba1c` | One per exam. Diabetic: from the exam's glucose (ADAG), at least 6.5 %. Otherwise about 5.3 %, nudged by glucose and age. |
| `measurement` | `serum_creatinine` | One per exam. Sex baseline, rising with age, hypertension and diabetes. |
| `measurement` | `egfr` | Computed from that creatinine with CKD-EPI 2021, so the two always agree. |
| `measurement` | `acr` | Log-normal around 8 mg/g, higher with diabetes, hypertension and systolic ≥ 140. |

- Documents, OCR output and every other table are not touched.
- Values come from `md5(patient_id)`, not `random()`, so every run gives the same data.
- Safe to re-run: it fills only empty patient fields and skips measurements that already exist.
- Synthetic measurements have `source = 'lab'` and point to the `ingestion_batch` with `source_uri = 'synthetic://004_synthetic_fill'`. To remove them:
  `DELETE FROM cardia.measurement WHERE source = 'lab' AND indicator_code IN ('hba1c','serum_creatinine','egfr','acr');`
- The phone numbers are random and could belong to real people, so never call or text them from the app.

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

Only original Framingham variables are used: the synthetic labs from `004` (HbA1c, creatinine, eGFR, ACR) are left out.

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

MVP without S3: same `document` row with `storage_backend = 'postgres'` and the bytes in `document_blob`. Bucket and key are still filled in with the values above, so the later move to S3 is a copy plus an update of `storage_backend`.
