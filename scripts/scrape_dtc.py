import os
import json
import requests
from bs4 import BeautifulSoup
import time

# --- 헌법 준수 (Safety Guardrails) ---
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_DOMAINS = ['obd-codes.com', 'autocodes.com']
RETRY_LIMIT = 3
DELAY_BETWEEN_REQUESTS = 1.5 # 사이트 부하 방지용 딜레이
# -----------------------------------

def get_dtc_info(code):
    url = f"https://www.obd-codes.com/{code.lower()}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for i in range(RETRY_LIMIT):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                main_div = soup.select_one('div.main')
                if not main_div: return None

                sections = {}
                headers_in_main = main_div.find_all('h2')
                for header in headers_in_main:
                    section_title = header.get_text(strip=True)
                    section_content = []
                    next_node = header.find_next_sibling()
                    while next_node and next_node.name != 'h2':
                        if next_node.name in ['p', 'ul', 'li', 'div']:
                            text = next_node.get_text(strip=True)
                            if text: section_content.append(text)
                        next_node = next_node.find_next_sibling()
                    if section_content: sections[section_title] = section_content

                full_text = "\n\n".join([f"### {k}\n" + "\n".join(v) for k, v in sections.items()])
                
                return {
                    "code": code.upper(),
                    "title": soup.title.string.strip() if soup.title else code.upper(),
                    "source_url": url,
                    "category": "DTC_SUMMARY",
                    "original_context": full_text[:5000],
                    "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            elif response.status_code == 404:
                return {"error": "404 Not Found"}
        except Exception:
            time.sleep(1)
    return None

if __name__ == "__main__":
    # 파레토 법칙: 가장 빈번한 핵심 DTC 코드 50개 (테스트용으로 50개만 우선 진행)
    common_codes = [
        "P0101", "P0171", "P0174", "P0300", "P0301", "P0302", "P0303", "P0304", 
        "P0420", "P0442", "P0455", "P0113", "P0118", "P0128", "P0135", "P0141",
        "P0201", "P0234", "P0299", "P0325", "P0335", "P0340", "P0401", "P0440",
        "P0505", "P0507", "P0606", "P0700", "P1135", "P1155", "P1349", "P2187"
    ]
    
    results = []
    print(f"Starting batch collection for {len(common_codes)} codes...")
    
    for code in common_codes:
        print(f"Propcessing {code}...")
        data = get_dtc_info(code)
        if data and "error" not in data:
            results.append(data)
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
    output_path = "data/dtc/batch_dtc_summary.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
        
    print(f"Batch collection complete. Saved {len(results)} records to {output_path}")
