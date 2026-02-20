# -*- coding: utf-8 -*-
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED = PROJECT / "db" / "seed_car_models.csv"

def has_hangul(s):
    return s and any("\uAC00" <= c <= "\uD7A3" for c in s)

rows = list(csv.DictReader(SEED.open(encoding="utf-8")))
seen = set()
for r in rows:
    key = (r["manufacturer_en"], r["model_name_en"])
    if key in seen:
        continue
    seen.add(key)
    ko = (r.get("model_name_ko") or "").strip()
    need = "NEED_KO" if not has_hangul(ko) else ""
    print(r["manufacturer_en"], "|", r["model_name_en"], "|", (ko[:50] if ko else ""), need)
