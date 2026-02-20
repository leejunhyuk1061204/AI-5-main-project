# -*- coding: utf-8 -*-
"""
Extract INSERT rows from db/seed_dtc_data.sql into CSV for \\copy.
Parses single INSERT with 7 columns (code, manufacturer, description_ko, description_en, summary_ko, summary_en, tts_phrase).
"""
import csv
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED_SQL = PROJECT / "db" / "seed_dtc_data.sql"
OUT_CSV = PROJECT / "db" / "seed_dtc_data.csv"

COLUMNS = ["code", "manufacturer", "description_ko", "description_en", "summary_ko", "summary_en", "tts_phrase"]


def read_sql_string(s: str, i: int):
    """Read a single-quoted SQL string starting at i. Returns (value, new_index). Escaped '' -> '."""
    if i >= len(s) or s[i] != "'":
        raise ValueError(f"Expected ' at {i}")
    i += 1
    start = i
    parts = []
    while i < len(s):
        if s[i] == "'":
            if i + 1 < len(s) and s[i + 1] == "'":
                parts.append(s[start:i])
                parts.append("'")
                i += 2
                start = i
            else:
                parts.append(s[start:i])
                return "".join(parts), i + 1
        else:
            i += 1
    raise ValueError("Unclosed quote")


def extract_rows(text: str):
    """Extract 7-tuples from VALUES (...), (...), ... up to ON CONFLICT."""
    vals_start = text.find("VALUES")
    if vals_start == -1:
        raise ValueError("VALUES not found")
    conflict_start = text.find("ON CONFLICT", vals_start)
    if conflict_start == -1:
        conflict_start = len(text)
    block = text[vals_start:conflict_start]
    i = block.find("(")
    rows = []
    while i < len(block):
        i += 1
        row = []
        for _ in range(7):
            while i < len(block) and block[i] in " \t\n\r":
                i += 1
            if i >= len(block) or block[i] != "'":
                break
            val, i = read_sql_string(block, i)
            row.append(val)
            while i < len(block) and block[i] in " \t\n\r,":
                i += 1
        if len(row) == 7:
            rows.append(row)
        while i < len(block) and block[i] != "(":
            i += 1
        if i >= len(block):
            break
    return rows


def main():
    text = SEED_SQL.read_text(encoding="utf-8")
    rows = extract_rows(text)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
