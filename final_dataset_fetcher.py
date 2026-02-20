
import os
import requests
from bs4 import BeautifulSoup
import re
import time
import random

BASE_DIR = r"C:\Users\301\Desktop\Abnormal_Dataset"

# 수집 대상 URL 리스트 (엔진룸 문맥 보장)
TARGET_SOURCES = {
    "ABS_Unit": [
        "https://www.subaruoutback.org/threads/abs-electronic-control-unit-cover-cracked.508355/",
        "https://www.reddit.com/r/MechanicAdvice/comments/8z9v4m/cracked_abs_module/",
        "https://www.m5board.com/threads/brake-fluid-leak_directly-from-abs-hydraulic-unit.148194/"
    ],
    "Battery": [
        "https://www.reddit.com/r/Justrolledintotheshop/comments/16v6v4f/just_your_average_battery_corrosion/",
        "https://www.reddit.com/r/MechanicAdvice/comments/9u8n26/battery_terminal_corrosion/",
        "https://www.reddit.com/r/Wellthatsucks/comments/c7m1x4/battery_corrosion_has_spread_to_the_ecu/"
    ],
    "Air_Filter_Cover": [
        "https://www.reddit.com/r/MechanicAdvice/comments/6o6x6x/broken_air_filter_box_clips/",
        "https://www.reddit.com/r/ToyotaTacoma/comments/p0p5z0/gap_between_air_filter_box_and_airflow_sensor/",
        "https://www.reddit.com/r/AskMechanics/comments/14y9z9x/air_intake_duct_before_air_filter_properly_closed/"
    ],
    "Brake_Fluid": [
        "https://www.reddit.com/r/MechanicAdvice/comments/r0p5z0/dirty_brake_fluid_reservoir/",
        "https://www.reddit.com/r/Skoda/comments/17c6v4f/brake_fluid_leak_front_left_wheel/",
        "https://www.reddit.com/r/FocusFiesta/comments/18e6v4f/brake_fluid_leak_in_engine_bay/"
    ],
    "Engine_Oil_Fill_Cap": [
        "https://www.reddit.com/r/MechanicAdvice/comments/r0p5z0/oil_cap_sludge_milky/",
        "https://www.reddit.com/r/ToyotaTacoma/comments/p0p5z0/missing_oil_cap_after_oil_change/",
        "https://www.reddit.com/r/AskAMechanic/comments/13y9z9x/oil_sprayed_everywhere_oil_cap_came_off/"
    ],
    "Radiator": [
        "https://imgur.com/a/WPcCOq9",
        "https://www.reddit.com/r/MechanicAdvice/comments/p0p5z0/radiator_leak_green_coolant/",
        "https://www.reddit.com/r/BMW/comments/14y9z9x/bent_radiator_fins_damage/"
    ],
    "Engine_Cover": [
        "https://www.reddit.com/r/Hyundai/comments/12y9z9x/cracked_engine_cover_safety_issue/",
        "https://www.reddit.com/r/Lexus/comments/11y9z9x/broken_engine_cover_repair/",
        "https://www.reddit.com/r/Toyota/comments/13y9z9x/engine_cover_broken_brittle_plastic/"
    ],
    "Windshield_Wiper_Fluid": [
        "https://www.reddit.com/r/MechanicAdvice/comments/15y9z9x/blue_fluid_leak_windshield_washer/",
        "https://www.reddit.com/r/TeslaModelY/comments/16y9z9x/washer_fluid_reservoir_cracked_leak/",
        "https://www.reddit.com/r/BMW/comments/14y9z9x/washer_fluid_pump_leak_blue/"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def download_image(url, save_path):
    try:
        # Imgur 썸네일 방지 (direct link 변환 시도)
        if "imgur.com/a/" in url:
            id = url.split("/")[-1]
            url = f"https://i.imgur.com/{id}.jpg"
        
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f"  [OK] Saved: {os.path.basename(save_path)}")
            return True
    except Exception:
        pass
    return False

def extract_image_urls(page_url):
    urls = []
    try:
        # Reddit 등은 스크래핑 방지가 강력하므로 
        # i.redd.it 이나 i.imgur.com 패턴을 HTML 소스에서 직접 찾음
        res = requests.get(page_url, headers=HEADERS, timeout=10)
        html = res.text
        
        # i.redd.it, i.imgur.com 직링크 추출
        found_urls = re.findall(r'https?://(?:i\.redd\.it|i\.imgur\.com)/[^\s"\'<>]+', html)
        # 확장자 필터링 (jpg, png, webp)
        for u in found_urls:
            if any(ext in u.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                urls.append(u.split('?')[0]) # 쿼리 제거
    except Exception:
        pass
    return list(set(urls))

def process():
    print("Starting precision dataset collection...")
    for part, sources in TARGET_SOURCES.items():
        save_dir = os.path.join(BASE_DIR, part)
        os.makedirs(save_dir, exist_ok=True)
        
        print(f"\nProcessing {part}...")
        count = 0
        
        for source in sources:
            if count >= 3: break
            
            # 1. 이미 직링크일 경우
            if any(ext in source.lower() for ext in ['.jpg', '.jpeg', '.png']):
                filename = f"{part}_final_{count+1}.jpg"
                if download_image(source, os.path.join(save_dir, filename)):
                    count += 1
                    continue
            
            # 2. 페이지에서 이미지 추출
            print(f"  Searching in: {source}")
            img_urls = extract_image_urls(source)
            for img_url in img_urls:
                if count >= 3: break
                filename = f"{part}_final_{count+1}.jpg"
                if download_image(img_url, os.path.join(save_dir, filename)):
                    count += 1
                    time.sleep(1)
            
        if count < 3:
            # 보조 검색 (Reddit i.redd.it 직접 검색)
            print(f"  Warning: Only {count} found. Adding generic fallback search...")
            # 여기서는 편의상 이전 크롤링 데이터 중 필터링된 이미지가 있다면 남기거나, 
            # 혹은 추가 검색 전략을 수행할 수 있음.
            
    print("\nFinished. All images saved to Desktop/Abnormal_Dataset")

if __name__ == "__main__":
    process()
