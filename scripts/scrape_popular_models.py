import os
import json
import time
from bs4 import BeautifulSoup
import requests

# --- 헌법 준수 (Safety Guardrails) ---
DELAY_BETWEEN_REQUESTS = 2.0  # 차단 방지
OUTPUT_PATH = "data/manuals/popular_models.json"
# -----------------------------------

# 타겟: 현대 2010-2013 (지도에서 확인된 연식)
TARGET_YEARS = ["2010", "2011", "2012", "2013"]
BASE_URL = "https://charm.li/Hyundai/"

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"  Error: {e}")
    return None

def get_models_for_year(year):
    """해당 연식의 모델 목록 가져오기"""
    url = f"{BASE_URL}{year}/"
    soup = get_soup(url)
    if not soup:
        return []
    
    links = soup.select('div.main ul li a')
    models = []
    for link in links:
        model_name = link.get_text(strip=True)
        model_href = link.get('href', '')
        # href가 /로 시작하면 절대 경로
        if model_href.startswith('/'):
            full_url = f"https://charm.li{model_href}"
        else:
            full_url = f"{BASE_URL}{year}/{model_href}"
        models.append({
            "name": model_name,
            "url": full_url
        })
    return models

def scrape_model_content(url, year, model_name):
    """모델 페이지 콘텐츠 크롤링"""
    soup = get_soup(url)
    if not soup:
        return None
    
    main_div = soup.select_one('div.main')
    if not main_div:
        return None
    
    # 네비게이션 제거
    for nav in main_div.select('div.breadcrumb, div.nav'):
        nav.decompose()
    
    content = main_div.get_text(separator="\n", strip=True)
    if len(content) < 100:  # 너무 짧으면 스킵
        return None
    
    return {
        "brand": "Hyundai",
        "year": year,
        "model": model_name,
        "title": soup.title.string.strip() if soup.title else f"Hyundai {year} {model_name}",
        "source_url": url,
        "category": "MANUAL",
        "original_context": content[:10000],
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

def main():
    results = []
    
    print("="*50)
    print("Hyundai Popular Models Crawler")
    print("="*50)
    
    for year in TARGET_YEARS:
        print(f"\n[{year}] Fetching model list...")
        models = get_models_for_year(year)
        print(f"  Found {len(models)} models")
        
        # 상위 5개 모델만 크롤링 (시간 절약)
        for model in models[:5]:
            print(f"  Scraping: {model['name']}...")
            data = scrape_model_content(model['url'], year, model['name'])
            
            if data:
                results.append(data)
                print(f"    [OK] {len(data['original_context'])} chars")
            else:
                print(f"    [SKIP]")
            
            time.sleep(DELAY_BETWEEN_REQUESTS)
    
    # 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*50}")
    print(f"Complete! Saved {len(results)} pages to {OUTPUT_PATH}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
