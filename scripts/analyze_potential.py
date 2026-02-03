import json
import os

# Load discovered targets
discovered_path = "data/manuals/all_discovered_targets.json"
with open(discovered_path, "r", encoding="utf-8") as f:
    discovered = json.load(f)

# Load existing parsed files
parsed_dir = "data/manuals/parsed"
parsed_files = {f.replace('_full.json', '') for f in os.listdir(parsed_dir) if f.endswith('.json')}

missing_targets = []
brand_counts = {}

for item in discovered:
    brand = item["brand"]
    year = item["year"]
    model = item["model"]
    key = f"{brand}_{year}_{model.replace('%20', '_')}"
    
    brand_counts[brand] = brand_counts.get(brand, {"found": 0, "total": 0})
    brand_counts[brand]["total"] += 1
    
    if key not in parsed_files:
        missing_targets.append(item)
    else:
        brand_counts[brand]["found"] += 1

# Sort brands by total models found
sorted_brands = sorted(brand_counts.items(), key=lambda x: x[1]["total"], reverse=True)

print(f"Summary of Discovery vs Current (2010-2013)")
print(f"===========================================")
print(f"Total Discovered: {len(discovered)}")
print(f"Already Collected: {len(discovered) - len(missing_targets)}")
print(f"New Potential Targets: {len(missing_targets)}")

print("\nTop 20 Brands (Discovered vs Collected):")
for brand, stats in sorted_brands[:20]:
    missing = stats["total"] - stats["found"]
    print(f"- {brand:15}: {stats['found']:4} / {stats['total']:4} (Missing: {missing:4})")

# Save the new missing targets for review
with open("data/manuals/potential_new_targets.json", "w", encoding="utf-8") as f:
    json.dump(missing_targets, f, ensure_ascii=False, indent=2)

# Specific check for requested common brands in Korea
kr_popular = ["Nissan-Datsun", "Mazda", "Subaru", "Infiniti", "Lexus", "Cadillac", "Volvo", "Porsche"]
print("\nSpecific Brands of Interest:")
for brand in kr_popular:
    if brand in brand_counts:
        stats = brand_counts[brand]
        missing = stats["total"] - stats["found"]
        print(f"- {brand:15}: {stats['found']:4} / {stats['total']:4} (Missing: {missing:4})")
