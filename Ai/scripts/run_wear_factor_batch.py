# scripts/run_wear_factor_batch.py
import json
import csv
from pathlib import Path
import requests

# ===============================
# 설정
# ===============================
API_URL = "http://127.0.0.1:8000/api/v1/predict/wear-factor"

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_DIR = BASE_DIR / "samples" / "wear_factor" / "wear_factor_input"
OUTPUT_DIR = BASE_DIR / "samples" / "wear_factor" / "wear_factor_output"
RESULTS_CSV = BASE_DIR / "results" / "wear_factor_results.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)


def main():
    input_files = sorted(INPUT_DIR.glob("*.json"))
    if not input_files:
        raise FileNotFoundError(f"No input JSON files found in {INPUT_DIR}")

    rows = []

    for json_path in input_files:
        print(f"[POST] {json_path.name}")

        with open(json_path, encoding="utf-8") as f:
            payload = json.load(f)

        resp = requests.post(API_URL, json=payload)
        if resp.status_code != 200:
            print(f"[FAIL] {json_path.name} -> {resp.status_code}")
            continue

        result = resp.json()

        # output json 저장
        out_path = OUTPUT_DIR / json_path.name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # CSV row 구성
        row = {
            "file": json_path.name,
            "predicted_wear_factor": result.get("predicted_wear_factor"),
            "model_version": result.get("model_version"),
            "avg_rpm": payload["driving_habits"]["avg_rpm"],
            "idle_ratio": payload["driving_habits"]["idle_ratio"],
            "hard_accel_count": payload["driving_habits"]["hard_accel_count"],
            "hard_brake_count": payload["driving_habits"]["hard_brake_count"],
        }
        rows.append(row)

        print(f"[OK] -> {out_path.relative_to(BASE_DIR)}")

    # 결과 CSV 저장
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] Saved results -> {RESULTS_CSV.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
