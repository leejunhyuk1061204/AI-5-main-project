import os
import time
import requests

# --- 설정 ---
OUTPUT_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
DELAY = 2

# 2025년 한국 점유율 및 2010-2011 인기 모델 기반 리스트
TARGETS = [
    # === 현대 (Hyundai) - 국산 1위 ===
    ("Hyundai", "2024", "Santa%20Fe%20L4-2.5L%20Turbo"), 
    ("Hyundai", "2024", "Grandeur%20V6-3.5L"),
    ("Hyundai", "2024", "Avante%20L4-1.6L"),
    ("Hyundai", "2011", "Elantra%20L4-1.8L"), # 아반떼 MD
    ("Hyundai", "2010", "Elantra%20L4-2.0L"), # 아반떼 HD/MD 전환기
    ("Hyundai", "2011", "Sonata%20L4-2.4L"),  # 쏘나타 YF
    ("Hyundai", "2010", "Sonata%20L4-2.4L"),  # 쏘나타 YF
    ("Hyundai", "2011", "Azera%20V6-3.3L"),    # 그랜저 HG
    ("Hyundai", "2010", "Azera%20V6-3.3L"),    # 그랜저 TG/HG 전환기
    ("Hyundai", "2011", "Tucson%20L4-2.0L"),   # 투싼 ix
    
    # === 기아 (Kia) - 국산 2위 ===
    ("Kia", "2024", "Sorento%20L4-2.5L%20Turbo"),
    ("Kia", "2024", "Carnival%20V6-3.5L"),
    ("Kia", "2024", "Sportage%20L4-1.6L%20Turbo"),
    ("Kia", "2011", "Optima%20L4-2.4L"),      # K5 1세대
    ("Kia", "2010", "Optima%20L4-2.4L"),      # 로체/K5 전환기
    ("Kia", "2011", "Sorento%20V6-3.5L"),     # 쏘렌토R
    ("Kia", "2011", "Sportage%20L4-2.4L"),    # 스포티지R
    ("Kia", "2011", "Soul%20L4-2.0L"),        # 쏘울
    
    # === BMW - 수입 1위 ===
    ("BMW", "2024", "530i%20xDrive%20%28G60%29%20L4-2.0L%20Turbo"),
    ("BMW", "2012", "528i%20%28F10%29%20L4-2.0L%20Turbo"), # 인기 중고 모델
    
    # === Mercedes Benz - 수입 2위 ===
    ("Mercedes%20Benz", "2024", "E%20350%204MATIC%20%28214.061%29%20L4-2.0L%20Turbo"),
    ("Mercedes%20Benz", "2011", "E%20350%20%28212.056%29%20V6-3.5L"), # 인기 중고 모델
    
    # === 기타 주요 모델 ===
    ("Genesis", "2024", "G80%20AWD%20V6-3.5L%20Turbo"),
    ("Chevrolet", "2011", "Cruze%20L4-1.8L"), # 크루즈 (라세티 프리미어)
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
        response = requests.get(url, headers=headers, stream=True, timeout=300)
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
    print("KR Popular Models Downloader (Ranked & 2010-2011)")
    print("="*60)
    
    for brand, year, model in TARGETS:
        download_zip(brand, year, model)
        time.sleep(DELAY)

if __name__ == "__main__":
    main()
