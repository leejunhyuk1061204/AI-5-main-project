import os
import time
import json
import requests
import subprocess
import sys
from datetime import datetime

# --- 설정 ---
TARGETS_JSON = "data/manuals/prioritized_targets.json"
OUTPUT_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
LOG_FILE = "logs/recovery_downloader.log"
PARSER_SCRIPT = "scripts/parse_manuals_to_json.py"

INITIAL_DELAY = 15  # 기본 대기 시간 (초)
MAX_DELAY = 300     # 최대 대기 시간 (5분)
BACKOFF_FACTOR = 2  # 429 에러 시 배수 적용

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

def run_parser():
    """파서 스크립트 실행 (다운로드된 ZIP을 JSON으로 변환 후 삭제)"""
    log("Running parser to process downloaded ZIPs...")
    try:
        # subprocess를 사용하여 별도 프로세스로 실행
        result = subprocess.run([sys.executable, PARSER_SCRIPT], capture_output=True, text=True, encoding="cp949", errors="replace")
        if result.returncode == 0:
            log("Parser finished successfully.")
            # 파서 출력 중 'Saved' 또는 'Deleting' 포함된 줄만 필터링해서 기록
            for line in result.stdout.splitlines():
                if "Saved" in line or "Deleting" in line or "Found" in line:
                    log(f"  [PARSER] {line.strip()}")
        else:
            log(f"Parser failed with return code {result.returncode}")
            log(f"Error: {result.stderr}")
    except Exception as e:
        log(f"Error running parser: {e}")

def download_zip(brand, year, model):
    filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
    filepath = os.path.join(OUTPUT_DIR, filename)
    url = f"https://charm.li/bundle/{brand}/{year}/{model}/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    current_delay = INITIAL_DELAY
    
    while True:
        log(f"Attempting download: {brand} {year} {model}")
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=900)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                log(f"  [SUCCESS] Saved {filename}")
                return True
            
            elif response.status_code == 429:
                log(f"  [RETRY] 429 Too Many Requests. Waiting {current_delay}s...")
                time.sleep(current_delay)
                current_delay = min(current_delay * BACKOFF_FACTOR, MAX_DELAY)
                continue
                
            elif response.status_code == 500:
                log(f"  [FAIL] 500 Internal Server Error for {url}")
                return False
            else:
                log(f"  [FAIL] Unexpected Status {response.status_code} for {url}")
                return False
                
        except Exception as e:
            log(f"  [ERROR] {e}")
            return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    log("="*60)
    log("Manual Recovery Downloader Started")
    log("="*60)
    
    if not os.path.exists(TARGETS_JSON):
        log(f"Error: Target file {TARGETS_JSON} not found.")
        return

    with open(TARGETS_JSON, "r", encoding="utf-8") as f:
        targets = json.load(f)
    
    log(f"Total targets to process: {len(targets)}")
    
    success_count = 0
    for i, (brand, year, model) in enumerate(targets):
        log(f"Progress: {i+1}/{len(targets)}")
        
        # 파일이 이미 파싱되었는지 한 번 더 확인 (중복 방지)
        parsed_name = f"{brand}_{year}_{model.replace('%20', '_')}_full.json"
        if os.path.exists(os.path.join(PARSED_DIR, parsed_name)):
            log(f"  [SKIP] Already parsed: {parsed_name}")
            continue

        if download_zip(brand, year, model):
            success_count += 1
            # 다운로드 성공 시마다 파서 실행 (디스크 공간 절약)
            run_parser()
            # 서버 부하 방지를 위한 기본 간격
            time.sleep(5)
        else:
            log(f"  [SKIPPING] Failed to download {brand} {year} {model}")
            time.sleep(10) # 실패 시 조금 더 대기

    log("="*60)
    log(f"Job Complete. Successfully added {success_count} manuals.")
    log("="*60)

if __name__ == "__main__":
    main()
