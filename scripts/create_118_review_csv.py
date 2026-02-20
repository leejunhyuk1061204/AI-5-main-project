# -*- coding: utf-8 -*-
"""Create db/seed_car_models_118_review.csv from download_list_summary_and_missing.txt section 2."""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
MISSING_TXT = PROJECT / "download_list_summary_and_missing.txt"
OUT_CSV = PROJECT / "db" / "seed_car_models_118_review.csv"


def main():
    text = MISSING_TXT.read_text(encoding="utf-8")
    # Section 2: lines like "  Audi | A3" until we hit "총 다운로드"
    in_section = False
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if "추가 필요 차종" in line or "seed에 없는" in line:
            in_section = True
            continue
        if in_section and (line.startswith("총 ") or not line):
            break
        if in_section and "|" in line:
            part = line.lstrip()
            if " | " in part:
                man_en, model_en = part.split(" | ", 1)
                model_en = model_en.replace("%2F", "/").strip()
                rows.append({
                    "manufacturer_ko": "",
                    "manufacturer_en": man_en.strip(),
                    "model_name_ko": "",
                    "model_name_en": model_en,
                    "year_start": "",
                    "year_end": "",
                    "fuel_types": "",
                })

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["manufacturer_ko", "manufacturer_en", "model_name_ko", "model_name_en", "year_start", "year_end", "fuel_types"],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")
    print("Fill manufacturer_ko, model_name_ko, year_start, year_end, fuel_types (comma-separated: GASOLINE,DIESEL,HEV)")


if __name__ == "__main__":
    main()
