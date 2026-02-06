import os
import time
import json
import requests
import random

# --- 설정 ---
OUTPUT_DIR = r"G:\내 드라이브\정비지침서\원본_zip"
PARSED_DIR = "data/manuals/parsed"
EMBEDDED_DIR = "data/manuals/embedded"
TARGET_LIST_PATH = "data/manuals/all_discovered_targets.json"
DELAY = 20  # 기본 20초 대기

def download_zip(brand, year, model, current_idx, total_count):
    filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
    filepath = os.path.join(OUTPUT_DIR, filename)
    parsed_filename = filename.replace('.zip', '_full.json')
    parsed_filepath = os.path.join(PARSED_DIR, parsed_filename)

    progress_str = f"[{current_idx}/{total_count}]"

    # 1. ZIP 파일 존재 여부만 체크 (JSON 존재 여부는 무시하고 다시 다운로드)
    # if os.path.exists(parsed_filepath):
    #     # 파싱된 파일이 이미 존재하면 스킵
    #     return True, False

    # if os.path.exists(embedded_filepath):
    #     # 임베딩까지 완료된 경우 스킵
    #     return True, False

    # 2. 이미 다운로드된 ZIP이 있는 경우 (중단된 경우 대비)
    if os.path.exists(filepath):
        if os.path.getsize(filepath) > 1024 * 1024:
            print(f"{progress_str} [READY] ZIP exists: {filename}")
            return True, False
        else:
            os.remove(filepath)

    url = f"https://charm.li/bundle/{brand}/{year}/{model}/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"{progress_str} Downloading {brand} {year} {model.replace('%20', ' ')}...")
    
    max_retries = 5
    retry_delay = 30 # 초기 재시도 대기 시간 (30초)
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=900)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"    [OK] Saved: {filename}")
                return True, True
            elif response.status_code == 429:
                wait_time = retry_delay * (2 ** attempt)
                print(f"    [429] Rate limit hit. Waiting {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"    [FAIL] Status: {response.status_code}")
                return False, True
        except Exception as e:
            print(f"    [ERROR] {e}")
            time.sleep(5)
            
    return False, True

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PARSED_DIR, exist_ok=True)
    
    print("="*60)
    print("Manual Downloader - Full Target List & Enhanced Retry")
    print("="*60)
    
    if not os.path.exists(TARGET_LIST_PATH):
        print(f"[ERROR] Target list not found: {TARGET_LIST_PATH}")
        return

    try:
        with open(TARGET_LIST_PATH, 'r', encoding='utf-8') as f:
            targets = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load target list: {e}")
        return

    total_targets = len(targets)
    print(f"Total Targets: {total_targets}")

    for i, item in enumerate(targets):
        current_idx = i + 1
        # 딕셔너리 형식 또는 리스트 형식 모두 대응
        if isinstance(item, dict):
            brand, year, model = item['brand'], item['year'], item['model']
        elif isinstance(item, list) and len(item) == 3:
            brand, year, model = item
        else:
            print(f"[WARN] Invalid item format: {item}")
            continue

        success, did_download = download_zip(brand, year, model, current_idx, total_targets)
        if did_download:
            # 지터(Jitter) 추가: 탐지 회피를 위해 랜덤하게 대기 시간 조절
            jitter = random.uniform(5, 15)
            time.sleep(DELAY + jitter)

if __name__ == "__main__":
    main()
