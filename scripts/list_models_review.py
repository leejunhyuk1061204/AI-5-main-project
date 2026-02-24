# -*- coding: utf-8 -*-
"""List distinct (manufacturer, model_en, model_ko) for manual review."""
import csv
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED = PROJECT / "db" / "seed_car_models.csv"

def has_hangul(s):
    return s and re.search(r"[\uAC00-\uD7A3]", s)

rows = list(csv.DictReader(SEED.open(encoding="utf-8")))
seen = {}
for r in rows:
    key = (r["manufacturer_en"], r["model_name_en"])
    if key not in seen:
        seen[key] = r["model_name_ko"]

# Sort by manufacturer, then model
for (man, mod_en), mod_ko in sorted(seen.items()):
    ko_has_hangul = "Y" if has_hangul(mod_ko) else "N"
    print(f"{man}\t{mod_en}\t{mod_ko}\t{ko_has_hangul}")
