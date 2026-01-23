import os
import time
import requests

# --- 설정 ---
OUTPUT_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
DELAY = 2

# 2010-2013 한국 및 글로벌 인기 모델 대규모 리스트
TARGETS = [
    # === Volvo ===
    ("Volvo", "2010", "XC60%20AWD%20L6-3.0L%20Turbo%20VIN%2099%20B6304T2"),
    ("Volvo", "2011", "XC60%20AWD%20L6-3.0L%20Turbo%20VIN%2090%20B6304T4"),
    ("Volvo", "2012", "S60%20T5%20FWD%20L5-2.5L%20Turbo%20VIN%2062%20B5254T5"),
    ("Volvo", "2013", "XC60%20AWD%20L6-3.2L%20VIN%2094%20B6324S4"),

    # === Porsche ===
    ("Porsche", "2010", "911%20Carrera%20%28997%29%20F6-3.6L"),
    ("Porsche", "2011", "Cayenne%20%2892A%29%20V6-3.6L"),
    ("Porsche", "2012", "911%20Carrera%20%28991%29%20F6-3.4L"),
    ("Porsche", "2013", "Cayenne%20%2892A%29%20V6-3.6L"),

    # === Jeep ===
    ("Jeep", "2011", "Grand%20Cherokee%204WD%20V6-3.6L"),
    ("Jeep", "2012", "Grand%20Cherokee%204WD%20V6-3.6L"),
    ("Jeep", "2013", "Grand%20Cherokee%204WD%20V6-3.6L"),

    # === Land Rover ===
    ("Land%20Rover", "2012", "Range%20Rover%20Evoque%20%28L538%29%20L4-2.0L%20Turbo"),
    ("Land%20Rover", "2013", "Range%20Rover%20Sport%20%28L320%29%20V8-5.0L%20SC"),

    # === Lexus ===
    ("Lexus", "2010", "RX%20350%20AWD%20V6-3.5L%20%282GR-FE%29"),
    ("Lexus", "2011", "ES%20350%20V6-3.5L%20%282GR-FE%29"),
    ("Lexus", "2012", "CT%20200h%20L4-1.8L%20%282ZR-FXE%29%20Hybrid"),

    # === BMW (Failed ones) ===
    ("BMW", "2011", "528i%20%28F10%29%20L6-3.0L"),
    ("BMW", "2012", "528i%20Sedan%20%28F10%29%20L4-2.0L%20Turbo%20%28N20%29"),
    ("BMW", "2013", "328i%20Sedan%20%28F30%29%20L4-2.0L%20Turbo%20%28N20%29"),

    # === Mercedes Benz (Failed ones) ===
    ("Mercedes%20Benz", "2011", "E%20350%20%28212.056%29%20V6-3.5L"),
    ("Mercedes%20Benz", "2012", "E%20350%20Sedan%20%28212.059%29%20V6-3.5L%20%28276.952%29"),
    ("Mercedes%20Benz", "2013", "C%20250%20Sedan%20%28204.047%29%20L4-1.8L%20Turbo%20%28271.860%29"),
]

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
        if os.path.getsize(filepath) > 1024 * 1024:
            print(f"  [READY] ZIP exists: {filename}")
            return True
        else:
            os.remove(filepath)

    url = f"https://charm.li/bundle/{brand}/{year}/{model}/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"  Downloading {brand} {year} {model.replace('%20', ' ')}...")
    try:
        # 타임아웃 600초로 상향
        response = requests.get(url, headers=headers, stream=True, timeout=600)
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
    print("Manual Downloader (600s Timeout)")
    print("="*60)
    
    for brand, year, model in TARGETS:
        download_zip(brand, year, model)
        time.sleep(DELAY)

if __name__ == "__main__":
    main()
