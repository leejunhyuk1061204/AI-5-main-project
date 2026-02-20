# -*- coding: utf-8 -*-
"""Parse missing_files_list.txt (연식 제외 차종별 요약) and compare with seed_car_models.sql."""
import re
from collections import defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
MISSING_LIST = PROJECT / "missing_files_list.txt"
SEED_SQL = PROJECT / "db" / "seed_car_models.sql"


def parse_download_line(line: str) -> tuple[str | None, str | None, str | None]:
    """Return (manufacturer, year, model) or (None, None, None). Model = base name before engine/spec."""
    line = line.strip().removesuffix(".zip")
    if not line:
        return None, None, None
    # Find _20XX_ to split maker and rest
    m = re.search(r"^(.+?)_(20\d{2})_(.+)$", line)
    if not m:
        return None, None, None
    manufacturer = m.group(1).replace("_", " ")  # Dodge and Ram, Land Rover, Mercedes Benz
    year = m.group(2)
    rest = m.group(3)
    # Model: take tokens until we hit engine-like (V6-, L4-, %28, 2WD, 4WD, AWD, FWD, RWD, _V8-, etc.)
    stop_pattern = re.compile(
        r"(_V\d+-\d|_L\d+-\d|_%\d|_2WD|_4WD|_AWD|_FWD|_RWD|_VIN_|_Turbo|_DSL|_Elect|_Hybrid|_Flex_Fuel|_SC_|_CNG)"
    )
    stop = stop_pattern.search(rest)
    model_part = rest[: stop.start()] if stop else rest
    # First meaningful segment as "base model" (drop trim like Sedan, Coupe for grouping)
    tokens = model_part.split("_")
    base_tokens = []
    for t in tokens:
        if t in ("Sedan", "Wagon", "Coupe", "Convertible", "Cabriolet", "Quattro", "AWD", "FWD", "RWD", "2WD", "4WD"):
            continue
        if re.match(r"^%\d", t) or re.match(r"^[A-Z]{2,3}\d*$", t):  # code like 4F2, 8RB
            break
        base_tokens.append(t)
    model = " ".join(base_tokens) if base_tokens else model_part.replace("_", " ")[:50]
    return manufacturer, year, model


def extract_seed_models(sql_path: Path) -> set[tuple[str, str]]:
    """Extract unique (manufacturer_en, base_model) from seed. Base model = model_name_en without (XXX)."""
    text = sql_path.read_text(encoding="utf-8")
    pattern = re.compile(r"\('([^']+)', '([^']+)', '[^']+', '([^']+)', \d{4}, ")
    seen = set()
    for m in pattern.finditer(text):
        man_ko, man_en, model_en = m.group(1), m.group(2), m.group(3)
        base = re.sub(r"\s*\([^)]+\)\s*$", "", model_en).strip()  # Elantra (MD) -> Elantra
        if base:
            seen.add((man_en, base))
    return seen


def main():
    lines = MISSING_LIST.read_text(encoding="utf-8").strip().splitlines()
    by_make_model = defaultdict(set)
    download_models = set()
    for line in lines:
        man, year, model = parse_download_line(line)
        if man and model:
            by_make_model[man].add(model)
            download_models.add((man, model))

    seed_set = extract_seed_models(SEED_SQL)

    manufacturer_normalize = {
        "Dodge and Ram": "Dodge",
        "Mercedes Benz": "Mercedes-Benz",
    }

    def norm_man(m: str) -> str:
        return manufacturer_normalize.get(m, m)

    seed_set_norm = set()
    for man, model in seed_set:
        seed_set_norm.add((norm_man(man), model))

    missing_for_seed = []
    for (man, model) in download_models:
        if (norm_man(man), model) not in seed_set_norm:
            if not re.match(r"^\d", model):
                missing_for_seed.append((man, model))

    missing_for_seed.sort(key=lambda x: (x[0], x[1]))
    missing_unique = []
    seen_m = set()
    for man, model in missing_for_seed:
        key = (norm_man(man), model)
        if key not in seen_m:
            seen_m.add(key)
            missing_unique.append((man, model))

    out_lines = []
    out_lines.append("=" * 60)
    out_lines.append("1. 다운로드 리스트 차종별 요약 (연식 제외)")
    out_lines.append("=" * 60)
    for man in sorted(by_make_model.keys()):
        models = sorted(by_make_model[man])
        out_lines.append(f"\n[{man}] ({len(models)}종)")
        for m in models:
            out_lines.append(f"  - {m}")

    out_lines.append("\n")
    out_lines.append("=" * 60)
    out_lines.append("2. seed_car_models.sql 대비 추가 필요 차종 (제조사·모델 기준)")
    out_lines.append("   (seed에 없는 다운로드 리스트 항목)")
    out_lines.append("=" * 60)
    for man, model in missing_unique:
        out_lines.append(f"  {man} | {model}")

    out_lines.append(f"\n총 다운로드 zip: {len(lines)}개")
    out_lines.append(f"차종별 고유 (제조사+모델): {len(download_models)}개")
    out_lines.append(f"추가 필요 (seed에 없음): {len(missing_unique)}건")

    result = "\n".join(out_lines)
    out_path = PROJECT / "download_list_summary_and_missing.txt"
    out_path.write_text(result, encoding="utf-8")
    print(result)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
