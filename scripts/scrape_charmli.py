import os
import json
import time
from bs4 import BeautifulSoup
import requests

# --- 헌법 준수 (Safety Guardrails) ---
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_DOMAINS = ['charm.li']
RETRY_LIMIT = 3
DELAY_BETWEEN_REQUESTS = 2.0
# -----------------------------------

def get_charmli_content(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for i in range(RETRY_LIMIT):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                main_div = soup.select_one('div.main')
                if not main_div: return None
                for nav in main_div.select('div.breadcrumb, div.nav'): nav.decompose()
                content = main_div.get_text(separator="\n", strip=True)
                return {
                    "title": soup.title.string.strip() if soup.title else "Manual Page",
                    "source_url": url,
                    "category": "MANUAL",
                    "original_context": content[:8000],
                    "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
        except Exception: time.sleep(1)
    return None

if __name__ == "__main__":
    # 베스트셀러 차종(2012 Sonata 등)의 핵심 정비 섹션 타겟
    base_url = "https://charm.li/Hyundai/2012/Sonata%20L4-2.4L/Repair%20and%20Diagnosis/Engine%2C%20Cooling%20and%20Exhaust/Engine/Service%20and%20Repair/"
    targets = [
        "Removal%20and%20Replacement/",
        "Overhaul/Disassembly/",
        "Overhaul/Reassembly/"
    ]
    
    results = []
    print(f"Starting batch manual collection for {len(targets)} pages...")
    for t in targets:
        url = base_url + t
        print(f"Scraping {url}...")
        data = get_charmli_content(url)
        if data: results.append(data)
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
    output_path = "data/manuals/batch_manuals.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"Batch manual scraping complete. Saved {len(results)} pages.")
