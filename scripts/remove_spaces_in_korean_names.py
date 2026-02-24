# -*- coding: utf-8 -*-
"""
Remove all spaces in manufacturer_ko and model_name_ko
in db/seed_car_models.csv and db/seed_car_models_118_review.csv.
e.g. "E 150" -> "E150", "Range Rover" -> "RangeRover"
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED_CSV = PROJECT / "db" / "seed_car_models.csv"
REVIEW_CSV = PROJECT / "db" / "seed_car_models_118_review.csv"


def remove_all_spaces(s: str) -> str:
    return (s or "").replace(" ", "")


def process_csv(path: Path, cols: list) -> int:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            rows.append(row)
    changed = 0
    for r in rows:
        for col in cols:
            val = (r.get(col) or "").strip()
            new_val = remove_all_spaces(val)
            if new_val != val:
                r[col] = new_val
                changed += 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return changed


def main():
    c1 = process_csv(SEED_CSV, ["manufacturer_ko", "model_name_ko"])
    c2 = process_csv(REVIEW_CSV, ["manufacturer_ko", "model_name_ko"])
    print(f"Removed all spaces: {SEED_CSV.name} {c1} cells, {REVIEW_CSV.name} {c2} cells.")


if __name__ == "__main__":
    main()
