import os
import time
import json
import requests

# --- 설정 ---
OUTPUT_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
PRIORITY_LIST_PATH = "data/manuals/prioritized_targets.json"
DELAY = 15  # 15초 대기

def download_zip(brand, year, model):
    filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
    filepath = os.path.join(OUTPUT_DIR, filename)
    parsed_filename = filename.replace('.zip', '_full.json')
    parsed_filepath = os.path.join(PARSED_DIR, parsed_filename)

    # 1. 이미 파싱된 경우 건너뛰기
    if os.path.exists(parsed_filepath):
        print(f"  [SKIP] Already parsed: {parsed_filename}")
        return True

    # 2. 이미 다운로드된 ZIP이 있는 경우 (중단된 경우 대비)
    if os.path.exists(filepath):
        if os.path.getsize(filepath) > 1024 * 1024: # 1MB 이상인 경우만 유효하다고 판단
            print(f"  [READY] ZIP exists: {filename}")
            return True
        else:
            os.remove(filepath)

    url = f"https://charm.li/bundle/{brand}/{year}/{model}/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"  Downloading {brand} {year} {model.replace('%20', ' ')}...")
    try:
        # 타임아웃 900초로 상향 (15분)
        response = requests.get(url, headers=headers, stream=True, timeout=900)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"    [OK] Saved: {filename}")
            return True
        else:
            print(f"    [FAIL] Status: {response.status_code}")
    except Exception as e:
        print(f"    [ERROR] {e}")
    return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PARSED_DIR, exist_ok=True)
    
    print("="*60)
    print("Priority Manual Downloader (2nd List)")
    print("="*60)
    
    if not os.path.exists(PRIORITY_LIST_PATH):
        print(f"[ERROR] Priority list not found: {PRIORITY_LIST_PATH}")
        return

    try:
        with open(PRIORITY_LIST_PATH, 'r', encoding='utf-8') as f:
            targets = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load priority list: {e}")
        return

    print(f"Total Targets: {len(targets)}")

    for item in targets:
        # JSON 리스트 형식이 [brand, year, model] 인지 확인 필요
        # track_all_progress.py 에서는 for brand, year, model in targets: 로 사용함
        if len(item) == 3:
            brand, year, model = item
            download_zip(brand, year, model)
            time.sleep(DELAY)
        else:
            print(f"[WARN] Invalid item format: {item}")

if __name__ == "__main__":
    main()
