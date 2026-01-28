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
    # Ford (2013 Popular)
    ("Ford", "2013", "Explorer%204WD%20V6-3.5L"),
    ("Ford", "2013", "Fusion%20AWD%20L4-2.0L%20Turbo"),
    ("Ford", "2013", "Escape%204WD%20L4-2.0L%20Turbo"),
    ("Ford", "2013", "Focus%20L4-2.0L"),
    
    # Lincoln (2013)
    ("Lincoln", "2013", "MKZ%20AWD%20V6-3.7L"),
    ("Lincoln", "2013", "MKX%20AWD%20V6-3.7L"),
    
    # Jaguar (2010-2013 Flagships)
    ("Jaguar", "2013", "XJ%20RWD%20%28X351%29%20V8-5.0L%20SC"),
    ("Jaguar", "2012", "XF%20%28X250%29%20V8-5.0L"),
    ("Jaguar", "2013", "XF%20RWD%20%28X250%29%20L4-2.0L%20Turbo"),
    
    # Volkswagen (2012-2013 Popular)
    ("Volkswagen", "2012", "Touareg%20%287P5%29%20V6-3.0L%20DSL%20Turbo%20%28CATA%29"),
    ("Volkswagen", "2013", "Beetle%20%285C1%29%20L4-2.0L%20Turbo%20%28CCTA%29"),
    ("Volkswagen", "2013", "CC%204Motion%20%28358%29%20V6-3.6L%20%28CNNA%29"),
    
    # Mini (Popular Trims)
    ("Mini", "2011", "Cooper%20S%20Countryman%20ALL4%20%28R60%29%20L4-1.6L%20Turbo%20%28N18%29"),
    ("Mini", "2012", "Cooper%20S%20Convertible%20%28R57%29%20L4-1.6L%20Turbo%20%28N18%29"),
    ("Mini", "2013", "Cooper%20JCW%20%28R56%29%20L4-1.6L%20Turbo%20%28N18%29"),
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
    print("Manual Downloader (600s Timeout)")
    print("="*60)
    
    for brand, year, model in TARGETS:
        download_zip(brand, year, model)
        time.sleep(DELAY)

if __name__ == "__main__":
    main()
