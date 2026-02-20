# -*- coding: utf-8 -*-
"""
Set model_name_ko to Korean for all rows, except English abbreviations/codes
(SRX, STS, RSX, MDX, TL, XF, E 150, K3, EV6, Genesis, G70, A3, M3, etc.).
"""
import csv
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SEED_CSV = PROJECT / "db" / "seed_car_models.csv"
REVIEW_CSV = PROJECT / "db" / "seed_car_models_118_review.csv"

# 영어 줄임말/코드명 -> 한글로 바꾸지 않고 그대로 둠
LEAVE_ENGLISH = frozenset({
    "SRX", "STS", "RSX", "MDX", "RDX", "TL", "RL", "ZDX", "ILX", "RLX", "TLX", "NSX", "ADX", "TSX",
    "XF", "XJ", "XK", "LR2", "EX35", "FX50", "G25", "G37", "G25x", "G37x",
    "M3", "M6", "A3", "A5", "A6", "A8", "A8L", "Q5", "Q7", "S6",
    "EV6", "EV9", "Genesis", "G70", "G80", "G90", "GV60", "GV70", "GV80",
    "E 150", "E 350", "E 450", "F 150", "F 450", "F 550",
})

def _leave_english(model_en: str) -> bool:
    if not model_en:
        return True
    if model_en in LEAVE_ENGLISH:
        return True
    if model_en.startswith(("K3 ", "K5 ", "K7 ", "K8 ")):
        return True
    if model_en.startswith(("E 150", "E 350", "E 450", "F 150", "F 450", "F 550")):
        return True
    if re.match(r"^[Kk]3\b", model_en) or re.match(r"^[Kk]5\b", model_en) or re.match(r"^[Kk]7\b", model_en) or re.match(r"^[Kk]8\b", model_en):
        return True
    if re.match(r"^[A-Z]\d+", model_en) and len(model_en) <= 6:
        return True
    return False

# (manufacturer_en, model_name_en) -> model_name_ko (한글, 띄어쓰기 없음)
KOREAN_MAP = {
    ("Kia", "Magentis"): "마젠티스",
    ("Kia", "Optima"): "옵티마",
    ("Kia", "Rio"): "리오",
    ("Kia", "Rondo"): "론도",
    ("Kia", "Sedona"): "세도나",
    ("Kia", "Soul"): "소울",
    ("Dodge", "Challenger"): "챌린저",
    ("Dodge", "Challenger SRT-8"): "챌린저SRT-8",
    ("Dodge", "Charger"): "차저",
    ("Dodge", "Charger SRT-8"): "차저SRT-8",
    ("Dodge", "Dakota"): "다코타",
    ("Dodge", "Durango"): "듀랑고",
    ("Dodge", "Grand Caravan"): "그랜드캐러번",
    ("Dodge", "Journey"): "저니",
    ("Ram", "RAM 1500 Truck"): "램1500",
    ("Ford", "Edge"): "에지",
    ("Ford", "Escape"): "이스케이프",
    ("Ford", "Expedition"): "익스페디션",
    ("Ford", "Explorer"): "익스플로러",
    ("Ford", "Mustang"): "머스탱",
    ("Ford", "Ranger"): "레인저",
    ("Ford", "Taurus"): "토러스",
    ("Ford", "Flex"): "플렉스",
    ("Ford", "Transit Connect"): "트랜짓커넥트",
    ("Ford", "Police Interceptor"): "폴리스인터셉터",
    ("Ford", "Police Interceptor Utility"): "폴리스인터셉터유틸리티",
    ("Chevrolet", "Avalanche"): "아발란치",
    ("Chevrolet", "Camaro"): "카마로",
    ("Chevrolet", "Corvette"): "콜벳",
    ("Chevrolet", "Cruze"): "크루즈",
    ("Chevrolet", "Equinox"): "이퀴녹스",
    ("Chevrolet", "Express 1500"): "익스프레스1500",
    ("Chevrolet", "Express 2500"): "익스프레스2500",
    ("Chevrolet", "Express 3500"): "익스프레스3500",
    ("Chevrolet", "Malibu"): "말리부",
    ("Chevrolet", "Silverado 1500"): "실버라도1500",
    ("Chevrolet", "Silverado 2500"): "실버라도2500",
    ("Chevrolet", "Tahoe"): "타호",
    ("Chevrolet", "Traverse"): "트래버스",
    ("Chevrolet", "Volt"): "볼트",
    ("Chevrolet", "Trax"): "트랙스",
    ("Chevrolet", "Trailblazer"): "트레일블레이저",
    ("Chevrolet", "Colorado"): "콜로라도",
    ("Acura", "Integra"): "인테그라",
    ("Acura", "TSX Sport Wagon"): "TSX스포츠웨건",
    ("Honda", "Element"): "엘리먼트",
    ("Honda", "Fit"): "핏",
    ("Honda", "Insight"): "인사이트",
    ("Honda", "Odyssey"): "오디세이",
    ("Honda", "Pilot"): "파일럿",
    ("Honda", "Ridgeline"): "리드라인",
    ("GMC", "Acadia"): "아카디아",
    ("GMC", "Savana 1500"): "사바나1500",
    ("GMC", "Savana 2500"): "사바나2500",
    ("GMC", "Savana 3500"): "사바나3500",
    ("GMC", "Savana 4500"): "사바나4500",
    ("GMC", "Sierra 1500"): "시에라1500",
    ("GMC", "Sierra 2500"): "시에라2500",
    ("GMC", "Sierra 2500 Denali"): "시에라2500데날리",
    ("GMC", "Sierra 3500"): "시에라3500",
    ("GMC", "Sierra 3500 Denali"): "시에라3500데날리",
    ("GMC", "Sierra Denali"): "시에라데날리",
    ("GMC", "Terrain"): "테레인",
    ("GMC", "Yukon"): "유콘",
    ("Buick", "Encore"): "앙코르",
    ("Buick", "LaCrosse"): "라크로스",
    ("Buick", "Regal"): "리갈",
    ("Buick", "Verano"): "베라노",
    ("Cadillac", "CTS Sedan"): "CTS세단",
    ("Cadillac", "CTS Wagon"): "CTS웨건",
    ("Cadillac", "Escalade"): "에스컬레이드",
    ("Cadillac", "Escalade/ESV"): "에스컬레이드ESV",
    ("BMW", "3 Series (F30)"): "3시리즈(F30)",
    ("BMW", "3 Series (G20)"): "3시리즈(G20)",
    ("BMW", "5 Series (F10)"): "5시리즈(F10)",
    ("BMW", "5 Series (G30)"): "5시리즈(G30)",
    ("BMW", "5 Series (G60)"): "5시리즈(G60)",
    ("BMW", "7 Series (G11)"): "7시리즈(G11)",
    ("BMW", "7 Series (G70)"): "7시리즈(G70)",
    ("BMW", "X5 (F15)"): "X5(F15)",
    ("BMW", "X5 (G05)"): "X5(G05)",
    ("BMW", "Alpina B7 xDrive"): "알피나B7x드라이브",
    ("BMW", "X1 sDrive 28i"): "X1s드라이브28i",
    ("BMW", "X1 xDrive 28i"): "X1x드라이브28i",
    ("BMW", "X1 xDrive 35i"): "X1x드라이브35i",
    ("BMW", "X3 xDrive 28i"): "X3x드라이브28i",
    ("BMW", "X3 xDrive 35i"): "X3x드라이브35i",
    ("BMW", "X5 M"): "X5M",
    ("BMW", "X5 xDrive 35d"): "X5x드라이브35d",
    ("BMW", "X5 xDrive 35i"): "X5x드라이브35i",
    ("BMW", "X5 xDrive 50i"): "X5x드라이브50i",
    ("Mercedes-Benz", "C-Class (W205)"): "C클래스(W205)",
    ("Mercedes-Benz", "C-Class (W206)"): "C클래스(W206)",
    ("Mercedes-Benz", "E-Class (W213)"): "E클래스(W213)",
    ("Mercedes-Benz", "E-Class (W214)"): "E클래스(W214)",
    ("Mercedes-Benz", "S-Class (W222)"): "S클래스(W222)",
    ("Mercedes-Benz", "S-Class (W223)"): "S클래스(W223)",
    ("Mercedes-Benz", "EQE/EQS"): "EQE/EQS",
    ("Mercedes Benz", "SL 63 AMG"): "SL63AMG",
    ("Mercedes Benz", "SL 65 AMG"): "SL65AMG",
    ("Tesla", "Model 3"): "모델3",
    ("Tesla", "Model Y"): "모델Y",
    ("Tesla", "Model S"): "모델S",
    ("Tesla", "Model X"): "모델X",
    ("Audi", "TT Quattro Coupe"): "TT쿼트로쿠페",
    ("Audi", "TT Quattro Roadster"): "TT쿼트로로드스터",
    ("Audi", "TTS Quattro Coupe"): "TTS쿼트로쿠페",
    ("Audi", "TTS Quattro Roadster"): "TTS쿼트로로드스터",
    ("Jeep", "Compass"): "컴패스",
    ("Jeep", "Grand Cherokee"): "그랜드체로키",
    ("Jeep", "Patriot"): "패트리어트",
    ("Land Rover", "Range Rover"): "레인지로버",
    ("Land Rover", "Range Rover Evoque"): "레인지로버에보크",
    ("Land Rover", "Range Rover Sport"): "레인지로버스포츠",
}

def has_hangul(s: str) -> bool:
    return bool(s and re.search(r"[\uAC00-\uD7A3]", s))


def apply_one(row: dict) -> str:
    man_en = (row.get("manufacturer_en") or "").strip()
    model_en = (row.get("model_name_en") or "").strip()
    current_ko = (row.get("model_name_ko") or "").strip()
    if _leave_english(model_en):
        return model_en.replace(" ", "")
    key = (man_en, model_en)
    if key in KOREAN_MAP:
        return KOREAN_MAP[key]
    if has_hangul(current_ko):
        return current_ko.replace(" ", "")
    return model_en.replace(" ", "")


def process(path: Path) -> int:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            rows.append(row)
    changed = 0
    for r in rows:
        new_ko = apply_one(r)
        if (r.get("model_name_ko") or "").strip() != new_ko:
            r["model_name_ko"] = new_ko
            changed += 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return changed


def main():
    c1 = process(SEED_CSV)
    c2 = process(REVIEW_CSV)
    print(f"Applied Korean model_name_ko: {SEED_CSV.name} {c1} rows, {REVIEW_CSV.name} {c2} rows.")


if __name__ == "__main__":
    main()
