from icrawler.builtin import GoogleImageCrawler
from pathlib import Path
import os

# 저장 경로 설정
SAVE_DIR = Path(r"C:\Users\301\Desktop\eofc")
SAVE_DIR.mkdir(parents=True, exist_ok=True)

def crawl_images(keyword, max_num=50):
    print(f"Start crawling '{keyword}'...")
    google_crawler = GoogleImageCrawler(
        feeder_threads=1,
        parser_threads=1,
        downloader_threads=4,
        storage={'root_dir': str(SAVE_DIR)}
    )
    
    # filters 인자 제거 및 단순 호출
    google_crawler.crawl(keyword=keyword, max_num=max_num)

if __name__ == "__main__":
    # 검색 키워드 리스트
    keywords = [
        "car engine oil filler cap close up",
        "dirty engine oil cap",
        "engine oil cap open"
    ]
    
    # 50장 채우기 위해 넉넉히 시도
    for kw in keywords:
        crawl_images(kw, max_num=20) # 키워드당 20장씩
        
    print(f"\nCrawling finished! Check: {SAVE_DIR}")
