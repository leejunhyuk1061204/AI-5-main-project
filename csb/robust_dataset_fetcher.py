
import os
import requests
import re
import time
import json

BASE_DIR = r"C:\Users\301\Desktop\Abnormal_Dataset"

# 검색 쿼리: 'engine bay' 또는 'under hood' 문맥 강제
QUERIES = {
    "ABS_Unit": "cracked ABS hydraulic unit engine bay car",
    "Battery": "severely corroded battery terminals under hood car",
    "Air_Filter_Cover": "broken air filter box gap under hood car",
    "Brake_Fluid": "leaking brake fluid master cylinder engine bay",
    "Engine_Oil_Fill_Cap": "engine oil fill cap sludge milky engine bay",
    "Radiator": "radiator leak coolant green engine compartment",
    "Engine_Cover": "cracked engine cover plastic engine bay car",
    "Windshield_Wiper_Fluid": "windshield washer fluid tank crack blue leak engine bay"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_ddg_images(query):
    # DuckDuckGo VQD 토큰 획득
    try:
        url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&t=h_&iax=images&ia=images"
        res = requests.get(url, headers=HEADERS, timeout=10)
        vqd = re.search(r'vqd=([^&]+)', res.text).group(1)
        
        # 이미지 검색 API 호출
        api_url = f"https://duckduckgo.com/i.js?l=wt-wt&o=json&q={query.replace(' ', '+')}&vqd={vqd}&f=,,,&p=1"
        res = requests.get(api_url, headers=HEADERS, timeout=10)
        data = res.json()
        return [r['image'] for r in data.get('results', [])]
    except Exception as e:
        print(f"Error fetching for {query}: {e}")
        return []

def download_image(url, save_path):
    try:
        # 이미 존재하는 파일이면 스킵 (크기 확인)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 20000:
            return True
            
        res = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        if res.status_code == 200:
            # 너무 작은 이미지(썸네일) 거르기 (20KB 미만)
            content = res.content
            if len(content) < 20000:
                return False
            with open(save_path, 'wb') as f:
                f.write(content)
            return True
    except:
        pass
    return False

def process():
    print("Starting robust collection (Engine Bay context focus)...")
    for part, query in QUERIES.items():
        save_dir = os.path.join(BASE_DIR, part)
        os.makedirs(save_dir, exist_ok=True)
        
        print(f"Collecting for {part}...")
        image_urls = get_ddg_images(query)
        
        count = 0
        for i, url in enumerate(image_urls):
            if count >= 3: break
            save_path = os.path.join(save_dir, f"{part}_robust_{count+1}.jpg")
            if download_image(url, save_path):
                print(f"  [OK] Downloaded image {count+1}")
                count += 1
                time.sleep(1)
            
    print("Done. Please check the Abnormal_Dataset folder on your Desktop.")

if __name__ == "__main__":
    process()
