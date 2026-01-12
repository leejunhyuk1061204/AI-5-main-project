import os
import json
import time
from bs4 import BeautifulSoup
import requests

# --- 헌법 준수 (Safety Guardrails) ---
DELAY = 1.5  # 차단 방지
OUTPUT_PATH = "data/manuals/repair_manuals_deep.json"
MAX_DEPTH = 3  # 최대 깊이 제한
# -----------------------------------

# 인기 모델 (시간 관계상 3개만)
TARGETS = [
    "https://charm.li/Hyundai/2012/Sonata%20L4-2.4L/",
    "https://charm.li/Hyundai/2012/Elantra%20L4-1.8L/",
    "https://charm.li/Hyundai/2013/Santa%20Fe%20L4-2.4L/",
]

def get_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"    Error: {e}")
    return None

def extract_content(soup):
    """실제 정비 내용 추출"""
    main_div = soup.select_one('div.main')
    if not main_div:
        return ""
    
    # 네비게이션 제거
    for nav in main_div.select('div.breadcrumb, div.nav, ul'):
        nav.decompose()
    
    # 텍스트 추출
    content = main_div.get_text(separator="\n", strip=True)
    return content

def crawl_section(url, section_name, depth=0):
    """섹션 재귀 크롤링"""
    if depth > MAX_DEPTH:
        return []
    
    results = []
    soup = get_soup(url)
    if not soup:
        return results
    
    main_div = soup.select_one('div.main')
    if not main_div:
        return results
    
    # 먼저 하위 링크 수집
    links = main_div.select('ul li a')
    sub_links = []
    for link in links[:5]:  # 각 레벨에서 5개만
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if href and not href.startswith('http') and not href.startswith('('):
            if href.startswith('/'):
                next_url = f"https://charm.li{href}"
            else:
                base = url if url.endswith('/') else url + '/'
                next_url = base + href
            sub_links.append((next_url, text))
    
    # 네비게이션 제거 후 콘텐츠 추출
    for nav in main_div.select('div.breadcrumb, div.nav, ul'):
        nav.decompose()
    
    content = main_div.get_text(separator="\n", strip=True)
    if len(content) > 200:  # 의미있는 콘텐츠만
        results.append({
            "section": section_name,
            "url": url,
            "content": content[:8000],
            "depth": depth
        })
        print(f"    {'  '*depth}[OK] {section_name[:40]}... ({len(content)} chars)")
    
    # 하위 링크 재귀 탐색
    for next_url, text in sub_links:
        time.sleep(DELAY)
        results.extend(crawl_section(next_url, text, depth + 1))
    
    return results

def main():
    all_results = []
    
    print("="*60)
    print("Deep Repair Manual Crawler")
    print("="*60)
    
    for target_url in TARGETS:
        model_name = target_url.split('/')[-2].replace('%20', ' ')
        print(f"\n[{model_name}]")
        
        # Repair and Diagnosis 섹션으로 이동
        repair_url = target_url + "Repair%20and%20Diagnosis/"
        
        sections = crawl_section(repair_url, "Repair and Diagnosis", depth=0)
        
        if sections:
            all_results.append({
                "model": model_name,
                "base_url": target_url,
                "sections": sections,
                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            print(f"  Total: {len(sections)} sections collected")
    
    # 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    total_sections = sum(len(r['sections']) for r in all_results)
    print(f"\n{'='*60}")
    print(f"Complete! {len(all_results)} models, {total_sections} sections")
    print(f"Saved to {OUTPUT_PATH}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
