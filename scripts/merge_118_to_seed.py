# -*- coding: utf-8 -*-
"""Merge db/seed_car_models_118_review.csv into db/seed_car_models.csv.
Review CSV must have year_start, year_end, fuel_types filled. Expands each row to
(year_start..year_end) x fuel_types and appends to seed_car_models.csv.
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REVIEW_CSV = PROJECT / "db" / "seed_car_models_118_review.csv"
SEED_CSV = PROJECT / "db" / "seed_car_models.csv"

HEADER = ["manufacturer_ko", "manufacturer_en", "model_name_ko", "model_name_en", "model_year", "fuel_type"]


def main():
    existing = SEED_CSV.read_text(encoding="utf-8").strip().splitlines()
    if not existing:
        raise SystemExit(f"{SEED_CSV} is empty or missing")

    new_rows = []
    with open(REVIEW_CSV, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            man_ko = (row.get("manufacturer_ko") or "").strip()
            man_en = (row.get("manufacturer_en") or "").strip()
            model_ko = (row.get("model_name_ko") or "").strip()
            model_en = (row.get("model_name_en") or "").strip()
            try:
                y1 = int((row.get("year_start") or "").strip())
                y2 = int((row.get("year_end") or "").strip())
            except ValueError:
                continue
            fuels_str = (row.get("fuel_types") or "").strip()
            if not fuels_str:
                continue
            fuels = [f.strip() for f in fuels_str.split(",") if f.strip()]
            if not fuels:
                continue
            if not man_ko or not model_ko:
                print(f"Skip (empty ko): {man_en} | {model_en}")
                continue
            for year in range(y1, y2 + 1):
                for fuel in fuels:
                    new_rows.append((man_ko, man_en, model_ko, model_en, year, fuel))

    if not new_rows:
        print("No rows to add. Fill year_start, year_end, fuel_types in review CSV.")
        return

    with open(SEED_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(new_rows)

    print(f"Appended {len(new_rows)} rows to {SEED_CSV} (total new: {len(new_rows)})")


if __name__ == "__main__":
    main()
