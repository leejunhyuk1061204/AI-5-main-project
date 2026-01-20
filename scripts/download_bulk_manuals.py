import os
import time
import requests

# --- 설정 ---
OUTPUT_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
DELAY = 2

# 2025년 한국 점유율 및 2010-2011 인기 모델 기반 리스트
TARGETS = [
    # === 현대 (Hyundai) ===
    ("Hyundai", "2010", "Elantra%20L4-2.0L"),
    ("Hyundai", "2011", "Elantra%20L4-1.8L"),
    ("Hyundai", "2012", "Elantra%20L4-1.8L"),
    ("Hyundai", "2013", "Elantra%20L4-1.8L"),
    ("Hyundai", "2010", "Sonata%20L4-2.4L"),
    ("Hyundai", "2011", "Sonata%20L4-2.4L"),
    ("Hyundai", "2012", "Sonata%20L4-2.4L"),
    ("Hyundai", "2013", "Sonata%20L4-2.4L"),
    ("Hyundai", "2010", "Azera%20V6-3.3L"),
    ("Hyundai", "2011", "Azera%20V6-3.3L"),
    ("Hyundai", "2012", "Azera%20V6-3.3L"),
    ("Hyundai", "2013", "Azera%20V6-3.3L"),
    
    # Tucson (Corrected: Requires FWD/AWD)
    ("Hyundai", "2010", "Tucson%20FWD%20L4-2.4L"),
    ("Hyundai", "2011", "Tucson%20FWD%20L4-2.0L"),
    ("Hyundai", "2012", "Tucson%20FWD%20L4-2.0L"),
    ("Hyundai", "2013", "Tucson%20FWD%20L4-2.0L"),
    ("Hyundai", "2010", "Tucson%20AWD%20L4-2.4L"),
    ("Hyundai", "2011", "Tucson%20AWD%20L4-2.4L"),
    ("Hyundai", "2012", "Tucson%20AWD%20L4-2.4L"),
    ("Hyundai", "2013", "Tucson%20AWD%20L4-2.4L"),
    
    ("Hyundai", "2010", "Santa%20Fe%20FWD%20L4-2.4L"),
    ("Hyundai", "2011", "Santa%20Fe%20FWD%20L4-2.4L"),
    ("Hyundai", "2012", "Santa%20Fe%20FWD%20L4-2.4L"),
    ("Hyundai", "2013", "Santa%20Fe%20FWD%20L4-2.4L"),
    
    # Genesis (Corrected: Requires Sedan/Coupe)
    ("Hyundai", "2010", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2011", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2012", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2013", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2010", "Genesis%20Coupe%20V6-3.8L"),
    ("Hyundai", "2011", "Genesis%20Coupe%20V6-3.8L"),
    ("Hyundai", "2012", "Genesis%20Coupe%20V6-3.8L"),
    ("Hyundai", "2013", "Genesis%20Coupe%20V6-3.8L"),

    # === 기아 (Kia) ===
    ("Kia", "2010", "Optima%20L4-2.4L"),
    ("Kia", "2011", "Optima%20L4-2.4L"),
    ("Kia", "2012", "Optima%20L4-2.4L"),
    ("Kia", "2013", "Optima%20L4-2.4L"),
    
    # Sorento (Corrected: 2010 missing, 2011-2013 requires 2WD/4WD and specific engine)
    ("Kia", "2011", "Sorento%202WD%20V6-3.5L"),
    ("Kia", "2012", "Sorento%202WD%20V6-3.5L"),
    ("Kia", "2013", "Sorento%202WD%20V6-3.5L"),
    ("Kia", "2011", "Sorento%202WD%20L4-2.4L"),
    ("Kia", "2012", "Sorento%202WD%20L4-2.4L%20VIN%206%20%28GDI%29"),
    ("Kia", "2013", "Sorento%202WD%20L4-2.4L%20VIN%206%20%28GDI%29"),
    
    # Sportage (Corrected: Requires 2WD/4WD)
    ("Kia", "2010", "Sportage%202WD%20L4-2.0L"),
    ("Kia", "2011", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2012", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2013", "Sportage%202WD%20L4-2.4L"),
    
    ("Kia", "2010", "Sedona%20V6-3.8L"),
    ("Kia", "2011", "Sedona%20V6-3.5L"),
    ("Kia", "2012", "Sedona%20V6-3.5L"),
    ("Kia", "2013", "Sedona%20V6-3.5L"),
    ("Kia", "2010", "Forte%20L4-2.0L"),
    ("Kia", "2011", "Forte%20L4-2.0L"),
    ("Kia", "2012", "Forte%20L4-2.4L"),
    ("Kia", "2013", "Forte%20L4-2.0L"),

    # === BMW ===
    ("BMW", "2010", "528i%20%28E60%29%20L6-3.0L"),
    ("BMW", "2011", "528i%20%28F10%29%20L6-3.0L"),
    ("BMW", "2012", "528i%20%28F10%29%20L4-2.0L%20Turbo"),
    ("BMW", "2013", "528i%20%28F10%29%20L4-2.0L%20Turbo"),

    # === Mercedes Benz ===
    ("Mercedes%20Benz", "2010", "E%20350%20%28212.056%29%20V6-3.5L"),
    ("Mercedes%20Benz", "2011", "E%20350%20%28212.056%29%20V6-3.5L"),
    ("Mercedes%20Benz", "2012", "E%20350%20Sedan%20%28212.059%29%20V6-3.5L%20%28276.952%29"),
    ("Mercedes%20Benz", "2013", "E%20350%20Sedan%20%28212.059%29%20V6-3.5L%20%28276.952%29"),
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
