-- Load car_model_master from CSV (same data as seed_car_models.sql).
-- Run from project root: psql -h ... -U ... -d ... -f db/seed_car_models_load.sql
-- FK: no other table REFERENCES car_model_master in schema, so CASCADE has no effect.
-- Wrapped in transaction so load is atomic; rollback on any error.

BEGIN;
TRUNCATE TABLE car_model_master RESTART IDENTITY CASCADE;
\copy car_model_master (manufacturer_ko, manufacturer_en, model_name_ko, model_name_en, model_year, fuel_type) FROM 'db/seed_car_models.csv' WITH (FORMAT csv, HEADER true);
COMMIT;
