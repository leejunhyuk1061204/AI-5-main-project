-- Load DTC seed from CSV (run from project root: psql ... -f db/seed_dtc_data_load.sql)
-- FK: dtc_history REFERENCES dtc_codes; dtc_freeze_frames REFERENCES dtc_history.
-- TRUNCATE CASCADE truncates dtc_codes, dtc_history, dtc_freeze_frames (seed reset).
-- Wrapped in transaction so load is atomic; rollback on any error.

BEGIN;
TRUNCATE TABLE dtc_codes CASCADE;
\copy dtc_codes (code, manufacturer, description_ko, description_en, summary_ko, summary_en, tts_phrase) FROM 'db/seed_dtc_data.csv' WITH (FORMAT csv, HEADER true);
COMMIT;
