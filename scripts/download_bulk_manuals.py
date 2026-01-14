import os
import time
import requests

# --- 설정 ---
OUTPUT_DIR = "data/manuals/zips"
DELAY = 3
# ---

# 수집 대상 모델 리스트 (현대/기아 중심 + 한국 인기 수입차)
TARGETS = [
    # === 현대 (Hyundai) ===
    ("Hyundai", "2012", "Genesis%20V6-3.8L"),           # 제네시스 BH
    ("Hyundai", "2013", "Genesis%20Coupe%20L4-2.0L%20Turbo"), # 제네시스 쿠페
    ("Hyundai", "2011", "Elantra%20L4-1.8L"),           # 아반떼 MD
    ("Hyundai", "2012", "Elantra%20L4-1.8L"),           # 아반떼 MD (Additional)
    ("Hyundai", "2013", "Elantra%20L4-1.8L"),           # 아반떼 MD (Additional)
    ("Hyundai", "2011", "Sonata%20L4-2.4L"),            # 쏘나타 YF
    ("Hyundai", "2012", "Sonata%20L4-2.4L"),            # 쏘나타 YF
    ("Hyundai", "2013", "Sonata%20L4-2.4L"),            # 쏘나타 YF
    ("Hyundai", "2012", "Azera%20V6-3.3L"),              # 그랜저 HG
    ("Hyundai", "2013", "Equus%20V8-5.0L"),              # 에쿠스 VI
    ("Hyundai", "2013", "Santa%20Fe%20Sport%20L4-2.0L%20Turbo"), # 싼타페 DM
    ("Hyundai", "2012", "Veloster%20L4-1.6L"),          # 벨로스터
    ("Hyundai", "2011", "Tucson%20L4-2.0L"),             # 투싼 ix
    ("Hyundai", "2013", "Accent%20L4-1.6L"),             # 엑센트 RB
    
    # === 기아 (Kia) ===
    ("Kia", "2011", "Optima%20L4-2.4L"),                # K5 (Additional)
    ("Kia", "2012", "Optima%20L4-2.4L"),                # K5
    ("Kia", "2013", "Optima%20L4-2.4L"),                # K5 (Additional)
    ("Kia", "2014", "Cadenza%20V6-3.3L"),               # K7
    ("Kia", "2012", "Forte%20L4-2.4L"),                 # 포르테
    ("Kia", "2011", "Sorento%20V6-3.5L"),               # 쏘렌토R (Additional)
    ("Kia", "2012", "Sorento%20V6-3.5L"),               # 쏘렌토R
    ("Kia", "2011", "Sportage%20L4-2.4L"),              # 스포티지R (Additional)
    ("Kia", "2012", "Sportage%20L4-2.4L"),              # 스포티지R
    ("Kia", "2013", "Sportage%20L4-2.4L"),              # 스포티지R (Additional)
    ("Kia", "2012", "Soul%20L4-2.0L"),                  # 쏘울
    ("Kia", "2012", "Sedona%20V6-3.5L"),                # 카니발
    ("Kia", "2013", "Rio%20L4-1.6L"),                   # 프라이드
    
    # === BMW ===
    ("BMW", "2012", "328i%20L4-2.0L%20Turbo"),          # 3시리즈 (F30)
    ("BMW", "2012", "528i%20L4-2.0L%20Turbo"),          # 5시리즈 (F10)
    ("BMW", "2011", "X5%20xDrive35i%20L6-3.0L%20Turbo"), # X5 (E70)
    ("BMW", "2012", "750Li%20V8-4.4L%20Turbo"),         # 7시리즈 (F02)
    
    # === Mercedes-Benz ===
    ("Mercedes-Benz", "2012", "C250%20L4-1.8L%20Turbo"), # C클래스 (W204)
    ("Mercedes-Benz", "2012", "E350%20V6-3.5L"),         # E클래스 (W212)
    ("Mercedes-Benz", "2012", "S550%20V8-4.6L%20Turbo"), # S클래스 (W221)
    ("Mercedes-Benz", "2013", "GLK350%20V6-3.5L"),       # GLK
    
    # === Audi ===
    ("Audi", "2012", "A4%20L4-2.0L%20Turbo"),            # A4
    ("Audi", "2012", "A6%20V6-3.0L%20Turbo"),            # A6
    ("Audi", "2012", "Q5%20V6-3.2L"),                    # Q5
    
    # === Lexus ===
    ("Lexus", "2012", "ES350%20V6-3.5L"),               # ES350
    ("Lexus", "2012", "RX350%20V6-3.5L"),               # RX350
    
    # === Volkswagen ===
    ("Volkswagen", "2012", "Tiguan%20L4-2.0L%20Turbo"),  # 티구안
    ("Volkswagen", "2012", "Golf%20L4-2.0L%20Turbo"),    # 골프
    ("Volkswagen", "2012", "Passat%20L4-2.0L%20Turbo"),  # 파사트
    
    # === Chevrolet (한국GM 공용 모델 중심) ===
    ("Chevrolet", "2012", "Cruze%20L4-1.4L%20Turbo"),    # 크루즈
    ("Chevrolet", "2013", "Malibu%20L4-2.5L"),           # 말리부
    ("Chevrolet", "2012", "Spark%20L4-1.2L"),            # 스파크
    ("Chevrolet", "2012", "Equinox%20L4-2.4L"),          # 에퀴녹스 (캡티바 유사)
    
    # === Toyota ===
    ("Toyota", "2012", "Camry%20L4-2.5L"),              # 캠리
    ("Toyota", "2012", "Prius%20L4-1.8L"),              # 프리우스
    
    # === Ford ===
    ("Ford", "2013", "Explorer%20V6-3.5L"),              # 익스플로러
]

def download_zip(brand, year, model):
    url = f"https://charm.li/bundle/{brand}/{year}/{model}/"
    filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    if os.path.exists(filepath):
        size_mb = os.path.getsize(filepath) / 1024 / 1024
        print(f"  [SKIP] Already exists: {filename} ({size_mb:.0f} MB)")
        return True

    # 2. 파싱된 데이터 확인 (parsed_manuals.json)
    parsed_filename = filename.replace('.zip', '_full.json')
    parsed_filepath = os.path.join("data/manuals/parsed", parsed_filename)

    if os.path.exists(parsed_filepath):
        print(f"  [SKIP] Already parsed: {parsed_filename}")
        return True
    
    # 지수 백오프 설정
    max_retries = 5
    base_delay = 5  # 초기 대기 시간 (초)
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print(f"  Downloading {brand} {year} {model.replace('%20', ' ')}...")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=600)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                size_mb = total_size / 1024 / 1024
                print(f"    Size: {size_mb:.1f} MB")
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                
                final_size = os.path.getsize(filepath) / 1024 / 1024
                print(f"    [OK] Saved: {filename} ({final_size:.0f} MB)")
                return True
                
            elif response.status_code == 429:
                wait_time = base_delay * (2 ** attempt) + (attempt * 2) # 지수 백오프
                print(f"    [429] Too Many Requests. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
                
            else:
                print(f"    [FAIL] Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"    [ERROR] {e}")
            time.sleep(base_delay)
            
    return False

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("="*60)
    print("Korea Popular Models Downloader")
    print(f"Target: {len(TARGETS)} models")
    print("="*60)
    
    success = 0
    for brand, year, model in TARGETS:
        if download_zip(brand, year, model):
            success += 1
        time.sleep(DELAY)
    
    # 최종 통계
    total_size = 0
    file_count = 0
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.zip'):
            total_size += os.path.getsize(os.path.join(OUTPUT_DIR, f))
            file_count += 1
    
    print(f"\n{'='*60}")
    print(f"Complete! {success}/{len(TARGETS)} downloaded")
    print(f"Total files: {file_count}")
    print(f"Total size: {total_size / 1024 / 1024 / 1024:.2f} GB")
    print("="*60)

if __name__ == "__main__":
    main()
