from icrawler.builtin import BingImageCrawler
from pathlib import Path
import os
import shutil
import uuid

def crawl_for_component(component_name, keywords, target_add_count=50):
    final_dir = Path(rf"C:\Users\301\Desktop\data\classification\{component_name}\train\normal")
    final_dir.mkdir(parents=True, exist_ok=True)
    
    temp_dir = Path(rf"C:\Users\301\Desktop\crawl_temp_{component_name}")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 키워드별로 넉넉히 수집
    num_per_kw = (target_add_count // len(keywords)) + 10
    
    for kw in keywords:
        print(f"\n>>> Crawling for [{component_name}] with keyword: '{kw}'")
        bing_crawler = BingImageCrawler(
            downloader_threads=4,
            storage={'root_dir': str(temp_dir)}
        )
        bing_crawler.crawl(keyword=kw, max_num=num_per_kw)
    
    # 임시 폴더에서 최종 폴더로 이동 (이름 중복 방지)
    new_files = list(temp_dir.glob("*.jpg")) + list(temp_dir.glob("*.png"))
    for f in new_files:
        new_name = f"crawl_{uuid.uuid4().hex[:8]}{f.suffix}"
        shutil.move(str(f), str(final_dir / new_name))
    
    shutil.rmtree(temp_dir)
    print(f"[SUCCESS] Added {len(new_files)} images to {component_name}")

if __name__ == "__main__":
    targets = {
        "Engine_Oil_Fill_Cap": [
            "car oil cap",
            "engine oil filler",
            "oil filler cap",
            "automotive oil cap",
            "car fluid cap",
            "under hood oil cap",
            "engine bay oil cap",
            "plastic oil cap",
            "metal oil cap",
            "custom oil cap",
            "racing oil cap",
            "billet oil cap"
        ]
    }
    
    for component, kws in targets.items():
        # 이미 52장이 있으므로, 100장을 더 추가하여 150장 수준을 목표로 함
        crawl_for_component(component, kws, target_add_count=100)
        
    print("\n[DONE] EOFC additional crawling tasks finished successfully.")
