-- Same as seed_car_models_load.sql but paths for docker initdb.d (do not run from host).
BEGIN;
TRUNCATE TABLE car_model_master RESTART IDENTITY CASCADE;
\copy car_model_master (manufacturer_ko, manufacturer_en, model_name_ko, model_name_en, model_year, fuel_type) FROM '/docker-entrypoint-initdb.d/seed_car_models.csv' WITH (FORMAT csv, HEADER true);
COMMIT;
