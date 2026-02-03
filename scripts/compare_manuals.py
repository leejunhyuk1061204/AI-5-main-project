import os
import sys

# Ensure scripts folder is in path
sys.path.append('scripts')
from download_bulk_manuals import TARGETS

parsed_dir = "data/manuals/parsed"
parsed_files = {f.replace('_full.json', '') for f in os.listdir(parsed_dir) if f.endswith('.json')}

ok_count = 0
fail_count = 0
brand_stats = {}

for brand, year, model in TARGETS:
    # Match the filename logic in download_bulk_manuals.py
    # filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
    key = f"{brand}_{year}_{model.replace('%20', '_')}"
    
    brand_stats.setdefault(brand, {"OK": 0, "TOTAL": 0})
    brand_stats[brand]["TOTAL"] += 1
    
    if key in parsed_files:
        ok_count += 1
        brand_stats[brand]["OK"] += 1
    else:
        fail_count += 1

print(f"Summary Report")
print(f"==============")
print(f"Total Targets: {len(TARGETS)}")
print(f"Successfully Parsed: {ok_count}")
print(f"Missing/Failed: {fail_count}")
print(f"Overall Progress: {ok_count/len(TARGETS)*100:.1f}%")

print("\nBrand-wise Statistics (sorted by % complete)")
print("------------------------------------------")
# Sort by completion percentage
sorted_brands = sorted(brand_stats.items(), 
                       key=lambda x: x[1]["OK"]/x[1]["TOTAL"] if x[1]["TOTAL"] > 0 else 0, 
                       reverse=True)

for brand, stats in sorted_brands:
    pct = (stats["OK"] / stats["TOTAL"]) * 100
    print(f"{brand:15}: {stats['OK']:3}/{stats['TOTAL']:3} ({pct:6.1f}%)")
