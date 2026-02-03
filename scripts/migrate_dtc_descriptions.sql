-- 1. Add description column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'dtc_codes' AND column_name = 'description') THEN
        ALTER TABLE dtc_codes ADD COLUMN description TEXT;
    END IF;
END $$;

-- 2. Migrate data from knowledge_dtc to dtc_codes
UPDATE dtc_codes dc
SET
    description = kd.description
FROM knowledge_dtc kd
WHERE
    dc.code = kd.code
    AND dc.manufacturer = kd.manufacturer;

-- 3. Drop knowledge_dtc table
DROP TABLE IF EXISTS knowledge_dtc;