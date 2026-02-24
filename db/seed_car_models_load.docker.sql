-- Same as seed_car_models_load.sql but paths for docker initdb.d (do not run from host).
BEGIN;

CREATE TEMP TABLE temp_car_model_master (
    LIKE car_model_master INCLUDING DEFAULTS
);

\copy temp_car_model_master (manufacturer_ko, manufacturer_en, model_name_ko, model_name_en, model_year, fuel_type) FROM '/docker-entrypoint-initdb.d/seed_car_models.csv' WITH (FORMAT csv, HEADER true);

INSERT INTO
    car_model_master (
        manufacturer_ko,
        manufacturer_en,
        model_name_ko,
        model_name_en,
        model_year,
        fuel_type
    )
SELECT
    manufacturer_ko,
    manufacturer_en,
    model_name_ko,
    model_name_en,
    model_year,
    fuel_type
FROM temp_car_model_master
ON CONFLICT (
    manufacturer_ko, model_name_ko, model_year, fuel_type
) DO NOTHING;

DROP TABLE temp_car_model_master;

COMMIT;