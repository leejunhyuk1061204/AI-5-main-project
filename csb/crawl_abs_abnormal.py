from icrawler.builtin import BingImageCrawler
from pathlib import Path
import os
import shutil
import uuid

def crawl_abnormal_abs_v2(target_total_count=50):
    base_dir = Path(r"C:\Users\301\Desktop\data\classification\ABS_Unit")
    train_abnormal = base_dir / "train" / "abnormal"
    test_abnormal = base_dir / "test" / "abnormal"
    
    temp_dir = Path(r"C:\Users\301\Desktop\crawl_temp_abs_abnormal_v2")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    keywords = [
        "ABS unit crack car engine bay",
        "broken ABS module plastic housing under hood",
        "ABS control unit casing damage installed",
        "car engine room ABS modulator dented",
        "ABS unit corner edge crack engine compartment",
        "damaged ABS hydraulic unit in car",
        "cracked ABS pump module car interior engine",
        "ABS module surface crack engine bay view",
        "broken ABS control module in vehicle",
        "ABS modulator impact damage",
        "corroded ABS module engine bay",
        "cracked car ABS unit assembly",
        "damaged ABS brake control module",
        "ABS hydraulic unit casing crack car",
        "failed ABS master cylinder",
        "ABS unit electrical connector damage",
        "cracked ABS reservoir car",
        "ABS modulator leaking oil",
        "car brake control unit crack",
        "corroded brake lines ABS unit",
        "damaged ABS solenoid block car"
    ]
    
    num_per_kw = (target_total_count // len(keywords)) + 20
    
    for kw in keywords:
        print(f"\n>>> Crawling for ABS defects with keyword: '{kw}'")
        bing_crawler = BingImageCrawler(
            downloader_threads=4,
            storage={'root_dir': str(temp_dir)}
        )
        bing_crawler.crawl(keyword=kw, max_num=num_per_kw)
    
    # Collect and Move
    all_files = list(temp_dir.glob("*.jpg")) + list(temp_dir.glob("*.png")) + list(temp_dir.glob("*.jpeg"))
    print(f"\n[INFO] Total {len(all_files)} images collected.")
    
    # Split: 85% Train, 15% Test
    split_idx = int(len(all_files) * 0.85)
    
    import random
    random.shuffle(all_files)
    
    train_files = all_files[:split_idx]
    test_files = all_files[split_idx:]
    
    def move_files(files, target_path):
        for f in files:
            new_name = f"abnormal_v2_{uuid.uuid4().hex[:8]}{f.suffix}"
            shutil.move(str(f), str(target_path / new_name))

    move_files(train_files, train_abnormal)
    move_files(test_files, test_abnormal)
    
    shutil.rmtree(temp_dir)
    print(f"[SUCCESS] Distributed {len(train_files)} to train and {len(test_files)} to test abnormal folders.")

if __name__ == "__main__":
    crawl_abnormal_abs_v2(target_total_count=100)
