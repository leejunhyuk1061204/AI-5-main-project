-- Same as seed_dtc_data_load.sql but paths for docker initdb.d (do not run from host).
BEGIN;
TRUNCATE TABLE dtc_codes CASCADE;
\copy dtc_codes (code, manufacturer, description_ko, description_en, summary_ko, summary_en, tts_phrase) FROM '/docker-entrypoint-initdb.d/seed_dtc_data.csv' WITH (FORMAT csv, HEADER true);
COMMIT;
