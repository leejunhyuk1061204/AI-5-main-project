import os
import json
import sys

# Ensure scripts folder is in path for imports
sys.path.append(os.path.dirname(__file__))

def check_list(targets, name):
    parsed_dir = "data/manuals/parsed"
    parsed_files = {f.replace('_full.json', '') for f in os.listdir(parsed_dir) if f.endswith('.json')}
    
    total = len(targets)
    done = 0
    brand_stats = {}
    
    for brand, year, model in targets:
        key = f"{brand}_{year}_{model.replace('%20', '_')}"
        brand_stats.setdefault(brand, {"OK": 0, "TOTAL": 0})
        brand_stats[brand]["TOTAL"] += 1
        
        if key in parsed_files:
            done += 1
            brand_stats[brand]["OK"] += 1
            
    print(f"\n[ {name} ]")
    print(f"Progress: {done}/{total} ({done/total*100:.1f}%)")
    
    # Show brands that are in progress
    in_progress = {b: s for b, s in brand_stats.items() if 0 < s["OK"] < s["TOTAL"]}
    if in_progress:
        print("Brands in progress:")
        for b, s in sorted(in_progress.items()):
            print(f"  - {b:15}: {s['OK']:3}/{s['TOTAL']:3}")

try:
    # 1. Original Bulk List (886)
    from download_bulk_manuals import TARGETS as BULK_TARGETS
    check_list(BULK_TARGETS, "Original Bulk List (886)")
except Exception as e:
    print(f"Error checking bulk list: {e}")

try:
    # 2. New Priority List (2609)
    priority_path = "data/manuals/prioritized_targets.json"
    if os.path.exists(priority_path):
        with open(priority_path, 'r', encoding='utf-8') as f:
            priority_targets = json.load(f)
        check_list(priority_targets, "New 2nd Extension List (2609)")
except Exception as e:
    print(f"Error checking priority list: {e}")
