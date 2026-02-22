-- Same as seed_dtc_data_load.sql but paths for docker initdb.d (do not run from host).
BEGIN;

CREATE TEMP TABLE temp_dtc_codes ( LIKE dtc_codes INCLUDING DEFAULTS );

\copy temp_dtc_codes (code, manufacturer, description_ko, description_en, summary_ko, summary_en, tts_phrase) FROM '/docker-entrypoint-initdb.d/seed_dtc_data.csv' WITH (FORMAT csv, HEADER true);

INSERT INTO
    dtc_codes (
        code,
        manufacturer,
        description_ko,
        description_en,
        summary_ko,
        summary_en,
        tts_phrase
    )
SELECT
    code,
    manufacturer,
    description_ko,
    description_en,
    summary_ko,
    summary_en,
    tts_phrase
FROM temp_dtc_codes
ON CONFLICT (code, manufacturer) DO NOTHING;

DROP TABLE temp_dtc_codes;

COMMIT;