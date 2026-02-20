# -*- coding: utf-8 -*-
"""Extract INSERT rows from db/seed_car_models.sql into CSV for \\copy."""
import csv
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED_SQL = PROJECT / "db" / "seed_car_models.sql"
OUT_CSV = PROJECT / "db" / "seed_car_models.csv"

# Match: ('...', '...', '...', '...', 2010, '...'), or ); at end
ROW_PATTERN = re.compile(
    r"\s*\('([^']*)', '([^']*)', '([^']*)', '([^']*)', (\d{4}), '([^']*)'\)"
)


def main():
    text = SEED_SQL.read_text(encoding="utf-8")
    rows = []
    for m in ROW_PATTERN.finditer(text):
        manufacturer_ko, manufacturer_en, model_name_ko, model_name_en, year, fuel = m.groups()
        rows.append((manufacturer_ko, manufacturer_en, model_name_ko, model_name_en, int(year), fuel))

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["manufacturer_ko", "manufacturer_en", "model_name_ko", "model_name_en", "model_year", "fuel_type"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
