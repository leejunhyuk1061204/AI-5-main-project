import os
import time
import requests

# --- 설정 ---
OUTPUT_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
DELAY = 2

# 2010-2013 한국 및 글로벌 인기 모델 대규모 리스트
TARGETS = [
    # === 현대 (Hyundai) ===
    ("Hyundai", "2010", "Elantra%20L4-2.0L"),
    ("Hyundai", "2011", "Elantra%20L4-1.8L"),
    ("Hyundai", "2012", "Elantra%20L4-1.8L"),
    ("Hyundai", "2013", "Elantra%20L4-1.8L"),
    ("Hyundai", "2011", "Sonata%20L4-2.4L"),
    ("Hyundai", "2012", "Sonata%20L4-2.4L"),
    ("Hyundai", "2013", "Sonata%20L4-2.4L"),
    ("Hyundai", "2011", "Azera%20V6-3.3L"),
    ("Hyundai", "2012", "Azera%20V6-3.3L"),
    ("Hyundai", "2013", "Azera%20V6-3.3L"),
    ("Hyundai", "2011", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2012", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2013", "Genesis%20Sedan%20V6-3.8L"),
    ("Hyundai", "2011", "Tucson%20FWD%20L4-2.0L"),
    ("Hyundai", "2012", "Tucson%20FWD%20L4-2.0L"),
    ("Hyundai", "2013", "Tucson%20FWD%20L4-2.4L"),
    ("Hyundai", "2012", "Santa%20Fe%20FWD%20L4-2.4L"),
    ("Hyundai", "2013", "Santa%20Fe%20FWD%20V6-3.3L"),
    ("Hyundai", "2011", "Accent%20L4-1.6L"),
    ("Hyundai", "2012", "Accent%20L4-1.6L"),
    ("Hyundai", "2013", "Accent%20L4-1.6L"),
    ("Hyundai", "2013", "Veloster%20L4-1.6L"),

    # === 기아 (Kia) ===
    ("Kia", "2011", "Optima%20L4-2.4L"),
    ("Kia", "2012", "Optima%20L4-2.4L"),
    ("Kia", "2013", "Optima%20L4-2.4L"),
    ("Kia", "2012", "Sorento%202WD%20L4-2.4L"),
    ("Kia", "2013", "Sorento%202WD%20L4-2.4L"),
    ("Kia", "2011", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2012", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2013", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2011", "Forte%20L4-2.0L"),
    ("Kia", "2012", "Forte%20L4-2.0L"),
    ("Kia", "2013", "Forte%20L4-2.0L"),
    ("Kia", "2011", "Rio%20L4-1.6L"),
    ("Kia", "2012", "Rio%20L4-1.6L"),
    ("Kia", "2013", "Rio%20L4-1.6L"),
    ("Kia", "2010", "Soul%20L4-2.0L"),
    ("Kia", "2011", "Soul%20L4-2.0L"),
    ("Kia", "2012", "Soul%20L4-2.0L"),
    ("Kia", "2013", "Soul%20L4-2.0L"),

    # === 쉐보레 (Chevrolet) ===
    ("Chevrolet", "2011", "Cruze%20L4-1.8L"),
    ("Chevrolet", "2012", "Cruze%20L4-1.8L"),
    ("Chevrolet", "2013", "Cruze%20L4-1.8L"),
    ("Chevrolet", "2011", "Malibu%20L4-2.4L"),
    ("Chevrolet", "2012", "Malibu%20L4-2.4L"),
    ("Chevrolet", "2013", "Malibu%20L4-2.5L"),
    ("Chevrolet", "2011", "Spark%20L4-1.2L"),
    ("Chevrolet", "2012", "Spark%20L4-1.2L"),
    ("Chevrolet", "2013", "Spark%20L4-1.2L"),
    # === 기아 (Kia) ===
    ("Kia", "2010", "Optima%20L4-2.4L"),
    ("Kia", "2011", "Optima%20L4-2.4L"),
    ("Kia", "2012", "Optima%20L4-2.4L"),
    ("Kia", "2013", "Optima%20L4-2.4L"),
    ("Kia", "2010", "Sorento%202WD%20L4-2.4L"),
    ("Kia", "2012", "Sorento%202WD%20L4-2.4L"),
    ("Kia", "2011", "Sorento%202WD%20V6-3.5L"),
    ("Kia", "2012", "Sorento%202WD%20V6-3.5L"),
    ("Kia", "2013", "Sorento%202WD%20V6-3.5L"),
    ("Kia", "2011", "Sorento%202WD%20L4-2.4L"),
    ("Kia", "2012", "Sorento%202WD%20L4-2.4L%20VIN%206%20%28GDI%29"),
    ("Kia", "2013", "Sorento%202WD%20L4-2.4L%20VIN%206%20%28GDI%29"),
    ("Kia", "2010", "Sportage%202WD%20L4-2.0L"),
    ("Kia", "2011", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2012", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2013", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2010", "Sportage%202WD%20L4-2.4L"),
    ("Kia", "2010", "Sedona%20V6-3.8L"),
    ("Kia", "2011", "Sedona%20V6-3.5L"),
    ("Kia", "2012", "Sedona%20V6-3.5L"),
    ("Kia", "2013", "Sedona%20V6-3.5L"),
    ("Kia", "2010", "Forte%20L4-2.0L"),
    ("Kia", "2011", "Forte%20L4-2.0L"),
    ("Kia", "2012", "Forte%20L4-2.4L"),
    ("Kia", "2013", "Forte%20L4-2.0L"),
    ("Kia", "2012", "Rio%20L4-1.6L"),
    ("Kia", "2011", "Soul%20L4-2.0L"),
    ("Kia", "2012", "Soul%20L4-2.0L"),

    # === 쉐보레 (Chevrolet/GM Korea) ===
    ("Chevrolet", "2013", "Spark%20L4-1.2L"),
    ("Chevrolet", "2011", "Malibu%20L4-2.4L"),
    ("Chevrolet", "2012", "Malibu%20L4-2.4L"),
    ("Chevrolet", "2010", "Equinox%20FWD%20L4-2.4L"),
    ("Chevrolet", "2011", "Equinox%20FWD%20L4-2.4L"),

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
