# -*- coding: utf-8 -*-
"""
Set model_name_ko = model_name_en for all rows in db/seed_car_models.csv.
Rule: manufacturer_ko stays as-is (한글); model name is unified to English
so we don't have to decide per-model (아큐라 인테그라 등도 영문으로).
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED_CSV = PROJECT / "db" / "seed_car_models.csv"


def main():
    rows = []
    with open(SEED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            rows.append(row)

    changed = 0
    for r in rows:
        en = (r.get("model_name_en") or "").strip()
        ko = (r.get("model_name_ko") or "").strip()
        if ko != en:
            r["model_name_ko"] = en
            changed += 1

    with open(SEED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Updated {SEED_CSV.name}: model_name_ko = model_name_en for {changed} rows (total {len(rows)}).")


if __name__ == "__main__":
    main()
