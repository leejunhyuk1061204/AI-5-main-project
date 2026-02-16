import os
import time
import json
import requests
import random

# --- 설정 ---
OUTPUT_DIR = r"G:\내 드라이브\정비지침서\원본_zip"
TARGET_LIST_PATH = "data/manuals/all_discovered_targets.json"
DELAY = 20  # 기본 20초 대기

def download_zip(brand, year, model, current_idx, total_count):
    filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
    filepath = os.path.join(OUTPUT_DIR, filename)

    progress_str = f"[{current_idx}/{total_count}]"

    # 이미 다운로드된 ZIP이 있는 경우 건너뛰기
    if os.path.exists(filepath):
        if os.path.getsize(filepath) > 1024 * 1024:
            print(f"{progress_str} [SKIP] ZIP already exists: {filename}")
            return True, False
        else:
            # 1MB 이하의 불완전한 파일은 삭제 후 다시 시도
            os.remove(filepath)

    url = f"https://charm.li/bundle/{brand}/{year}/{model}/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    print(f"{progress_str} Downloading (REVERSE) {brand} {year} {model.replace('%20', ' ')}...")
    
    max_retries = 5
    retry_delay = 30 
    
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
    
    print("="*60)
    print("Manual Downloader - REVERSE MODE (Starting from Bottom)")
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

    # 역순으로 정렬
    targets_reverse = targets[::-1]
    total_targets = len(targets_reverse)
    print(f"Total Targets: {total_targets} (Downloading in Reverse Order)")

    for i, item in enumerate(targets_reverse):
        current_idx = i + 1
        if isinstance(item, dict):
            brand, year, model = item['brand'], item['year'], item['model']
        elif isinstance(item, list) and len(item) == 3:
            brand, year, model = item
        else:
            continue

        success, did_download = download_zip(brand, year, model, current_idx, total_targets)
        
        if did_download:
            jitter = random.uniform(5, 15)
            time.sleep(DELAY + jitter)

if __name__ == "__main__":
    main()
