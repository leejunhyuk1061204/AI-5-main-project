# -*- coding: utf-8 -*-
"""
Survey: if we apply "domestic -> Korean model_name_ko, import -> English model_name_ko",
what would change in db/seed_car_models.csv?
"""
import csv
import re
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parents[1]
SEED_CSV = PROJECT / "db" / "seed_car_models.csv"

# Domestic = 국산 (use Korean for model_name_ko)
DOMESTIC_MANUFACTURERS_EN = {"Hyundai", "Kia"}
DOMESTIC_MANUFACTURERS_KO = {"현대", "기아"}

# 코드명/영문 유지 (i30, K3, K5, K7, K8, EV6, EV9, Genesis, RSX 등)
DOMESTIC_LEAVE_AS_IS_PREFIXES = ("K3 ", "K5 ", "K7 ", "K8 ", "EV6", "EV9", "Genesis", "i30", "RSX")
CODE_NAME_MODELS = frozenset({"EV6", "EV9", "Genesis", "i30", "RSX"})

def _domestic_leave_as_is(model_ko: str, model_en: str) -> bool:
    if model_ko in CODE_NAME_MODELS or model_en in CODE_NAME_MODELS:
        return True
    for p in DOMESTIC_LEAVE_AS_IS_PREFIXES:
        if model_ko.startswith(p) or model_en.startswith(p) or model_ko == p or model_en.startswith(p + " ") or model_en.startswith(p + "/"):
            return True
    return False

def has_hangul(s: str) -> bool:
    return bool(re.search(r"[\uAC00-\uD7A3]", s))

def main():
    rows = []
    with open(SEED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    domestic_english_ko = defaultdict(set)   # (man_ko, model_ko, model_en) -> set of (year, fuel) for distinct
    import_hangul_ko = defaultdict(set)

    for r in rows:
        man_ko = (r.get("manufacturer_ko") or "").strip()
        man_en = (r.get("manufacturer_en") or "").strip()
        model_ko = (r.get("model_name_ko") or "").strip()
        model_en = (r.get("model_name_en") or "").strip()
        is_domestic = man_en in DOMESTIC_MANUFACTURERS_EN or man_ko in DOMESTIC_MANUFACTURERS_KO

        if is_domestic:
            if not has_hangul(model_ko) and not _domestic_leave_as_is(model_ko, model_en):
                key = (man_ko, model_ko, model_en)
                domestic_english_ko[key].add((r.get("model_year"), r.get("fuel_type")))
        else:
            if has_hangul(model_ko):
                key = (man_ko, model_ko, model_en)
                import_hangul_ko[key].add((r.get("model_year"), r.get("fuel_type")))

    print("=" * 70)
    print("Rule: 국산 -> model_name_ko 한글 | 수입 -> model_name_ko 영문")
    print("=" * 70)
    print()

    # Domestic: currently model_name_ko is English -> would change to Korean (K3/K5/K7/K8/EV6/EV9/Genesis 제외)
    print("[1] 국산(현대, 기아) 중 model_name_ko가 한글이 아닌 것 (한글로 바꿀 대상, K3/K5/K7/K8/EV6/EV9/Genesis는 제외)")
    print("    -> 바꾸려면 model_name_en에 대응하는 한글명 매핑 필요")
    items = sorted(domestic_english_ko.items(), key=lambda x: (x[0][0], x[0][2]))
    if not items:
        print("    없음.")
    else:
        total_rows = sum(len(v) for _, v in items)
        print(f"    distinct (제조사_ko, model_ko, model_en): {len(items)}개, 영향 행 수: {total_rows}")
        for (man_ko, model_ko, model_en), pairs in items[:30]:
            print(f"      {man_ko} | {model_ko} -> (한글명 필요) | en: {model_en}")
        if len(items) > 30:
            print(f"      ... 외 {len(items) - 30}개")
    print()

    # Import: currently model_name_ko has Hangul -> would change to model_name_en
    print("[2] 수입(현대/기아 제외) 중 model_name_ko에 한글이 있는 것 (영문으로 바꿀 대상)")
    print("    -> model_name_ko = model_name_en 으로 치환하면 됨")
    items2 = sorted(import_hangul_ko.items(), key=lambda x: (x[0][0], x[0][2]))
    if not items2:
        print("    없음.")
    else:
        total_rows2 = sum(len(v) for _, v in items2)
        print(f"    distinct (제조사_ko, model_ko, model_en): {len(items2)}개, 영향 행 수: {total_rows2}")
        for (man_ko, model_ko, model_en), pairs in items2[:40]:
            print(f"      {man_ko} | {model_ko} -> {model_en}")
        if len(items2) > 40:
            print(f"      ... 외 {len(items2) - 40}개")
    print()

    print("=" * 70)
    print("Summary")
    print("=" * 70)
    d_count = sum(len(v) for _, v in domestic_english_ko.items())
    i_count = sum(len(v) for _, v in import_hangul_ko.items())
    print(f"  Domestic but model_name_ko has NO Hangul: {len(domestic_english_ko)} models, {d_count} rows (need KO mapping)")
    print(f"  Import but model_name_ko has Hangul: {len(import_hangul_ko)} models, {i_count} rows (replace with model_name_en)")
    print(f"  No change (already compliant): {len(rows) - d_count - i_count} rows")

    out = PROJECT / "db" / "survey_ko_en_changes.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write("Rule: domestic(현대,기아) -> model_name_ko 한글 | import -> model_name_ko 영문\n")
        f.write("      단, 국산 중 K3/K5/K7/K8/EV6/EV9/Genesis 계열은 그대로 둠.\n\n")
        f.write("[1] Domestic, model_name_ko has no Hangul (would need Korean name, K3/K5/K7/K8/EV6/EV9/Genesis excluded)\n")
        for (man_ko, model_ko, model_en), pairs in sorted(domestic_english_ko.items(), key=lambda x: (x[0][0], x[0][2])):
            f.write(f"  {man_ko} | {model_ko} | en: {model_en}\n")
        f.write(f"\n[2] Import, model_name_ko has Hangul (would set to model_name_en)\n")
        for (man_ko, model_ko, model_en), pairs in sorted(import_hangul_ko.items(), key=lambda x: (x[0][0], x[0][2])):
            f.write(f"  {man_ko} | {model_ko} -> {model_en}\n")
        f.write(f"\nSummary: domestic no-Hangul {len(domestic_english_ko)} models {d_count} rows; import Hangul {len(import_hangul_ko)} models {i_count} rows\n")
    print(f"\nWrote detail to {out}")


if __name__ == "__main__":
    main()
