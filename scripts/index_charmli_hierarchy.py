import os
import json
import time
import requests
from bs4 import BeautifulSoup

# --- 헌법 준수 (Safety Guardrails) ---
BASE_URL = "https://charm.li/"
OUTPUT_PATH = "data/manuals/charmli_hierarchy_map.json"
DELAY = 1.0  # 사이트 부하 방지
# -----------------------------------

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

def index_hierarchy():
    brands_soup = get_soup(BASE_URL)
    if not brands_soup:
        return
    
    # 1. 브랜드 목록 추출
    brand_links = brands_soup.select('div.main ul li a')
    hierarchy = {}
    
    print(f"Found {len(brand_links)} brands. Starting deep scan...")
    
    # 시간 관계상 모든 브랜드를 다 도는 것보다 상위 브랜드부터 전략적으로 스캔
    # (실제 대규모 스캔은 백그라운드에서 진행 권색)
    for link in brand_links[:20]: # 우선 상위 20개 브랜드 우선 스캔 (현대, 기아 등 포함)
        brand_name = link.get_text(strip=True)
        brand_href = link['href']
        brand_url = BASE_URL + brand_href.lstrip('/')
        
        print(f"Indexing brand: {brand_name}...")
        hierarchy[brand_name] = {"url": brand_url, "years": {}}
        
        # 2. 연식 추출
        years_soup = get_soup(brand_url)
        if not years_soup: continue
        
        year_links = years_soup.select('div.main ul li a')
        for y_link in year_links:
            year_val = y_link.get_text(strip=True)
            year_href = y_link['href']
            # 상대 경로 처리 (브랜드/연식 형식일 수 있음)
            year_url = brand_url + y_link['href']
            
            hierarchy[brand_name]["years"][year_val] = {"url": year_url}
            
        time.sleep(DELAY) # 매 브랜드 사이사이 딜레이
        
        # 중간 저장 (수시로)
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(hierarchy, f, indent=4, ensure_ascii=False)

    print(f"Hierarchy map (part 1) saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    index_hierarchy()
