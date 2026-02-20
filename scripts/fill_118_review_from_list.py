# -*- coding: utf-8 -*-
"""Fill seed_car_models_118_review.csv from missing_files_list.txt (filename only) + Korean name mapping."""
import csv
import re
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parents[1]
MISSING_LIST = PROJECT / "missing_files_list.txt"
REVIEW_CSV = PROJECT / "db" / "seed_car_models_118_review.csv"

MAN_KO = {
    "Audi": "아우디",
    "BMW": "BMW",
    "Buick": "뷰릭",
    "Cadillac": "캐딜락",
    "Chevrolet": "쉐보레",
    "Chrysler": "크라이슬러",
    "Dodge and Ram": "도지 앤 램",
    "Ford": "포드",
    "GMC": "GMC",
    "Honda": "혼다",
    "Hyundai": "현대",
    "Infiniti": "인피니티",
    "Jaguar": "재규어",
    "Jeep": "지프",
    "Kia": "기아",
    "Land Rover": "랜드로버",
    "Mazda": "마쯔다",
    "Mercedes Benz": "메르세데스-벤츠",
    "Acura": "아큐라",
}

def norm(s):
    return s.replace(" ", "_").replace("/", "_")

def fuel_from_filename(name):
    name_upper = name.upper()
    fuels = set()
    if "DSL" in name_upper or "_DSL_" in name_upper:
        fuels.add("DIESEL")
    if "HYBRID" in name_upper:
        fuels.add("HEV")
    if "ELECT" in name_upper:
        fuels.add("EV")
    if "CNG" in name_upper:
        fuels.add("LPG")
    if not fuels:
        fuels.add("GASOLINE")
    return fuels

def parse_zip_line(line):
    line = line.strip().removesuffix(".zip")
    if not line or not re.match(r"^.+\_20\d{2}\_", line):
        return None
    parts = line.replace("%2F", "/").split("_")
    year = None
    for i, p in enumerate(parts):
        if re.match(r"^20\d{2}$", p):
            year = int(p)
            break
    if not year:
        return None
    man_end = i
    manufacturer = "_".join(parts[:man_end]).replace("_", " ")
    rest = parts[man_end + 1:]
    model_tokens = []
    for p in rest:
        if re.match(r"^[VL]\d+-\d", p) or (p.startswith("%") and len(p) > 1) or p in ("2WD", "4WD", "AWD", "FWD", "RWD"):
            break
        model_tokens.append(p)
    model_slug = "_".join(model_tokens) if model_tokens else ""
    fuels = fuel_from_filename(line)
    return (manufacturer, year, model_slug, fuels)

def main():
    by_key = defaultdict(lambda: {"years": set(), "fuels": set()})
    for line in MISSING_LIST.read_text(encoding="utf-8").strip().splitlines():
        r = parse_zip_line(line)
        if not r:
            continue
        man, year, model_slug, fuels = r
        if not model_slug:
            continue
        by_key[(man, model_slug)]["years"].add(year)
        by_key[(man, model_slug)]["fuels"].update(fuels)

    rows = list(csv.DictReader(REVIEW_CSV.open(encoding="utf-8")))
    for row in rows:
        man_en = (row.get("manufacturer_en") or "").strip()
        model_en = (row.get("model_name_en") or "").strip()
        row["manufacturer_ko"] = MAN_KO.get(man_en, man_en)
        row["model_name_ko"] = row.get("model_name_ko") or model_en
        best = None
        best_len = -1
        model_norm = norm(model_en)
        for (m, slug), data in by_key.items():
            if m != man_en:
                continue
            slug_sp = slug.replace("_", " ")
            if slug == model_norm or slug_sp == model_en or (model_norm in slug and len(model_norm) >= 2) or (slug in model_norm) or model_en.startswith(slug_sp) or slug_sp.startswith(model_en):
                if len(data["years"]) > best_len:
                    best = data
                    best_len = len(data["years"])
        if best and best["years"]:
            row["year_start"] = min(best["years"])
            row["year_end"] = max(best["years"])
            row["fuel_types"] = ",".join(sorted(best["fuels"]))

    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["manufacturer_ko", "manufacturer_en", "model_name_ko", "model_name_en", "year_start", "year_end", "fuel_types"])
        w.writeheader()
        w.writerows(rows)
    print(f"Filled {REVIEW_CSV}")
    filled = sum(1 for r in rows if r.get("year_start") and r.get("fuel_types"))
    print(f"Rows with year/fuel: {filled}/{len(rows)}")

if __name__ == "__main__":
    main()
