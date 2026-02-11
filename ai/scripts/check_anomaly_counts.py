import os
import json
from pathlib import Path

root = Path("ai/data/anomaly")
extensions = (".jpg", ".png", ".jpeg")

results = {}
total_images = 0

for d in sorted(root.iterdir()):
    if d.is_dir():
        count = sum(1 for p in d.rglob("*") if p.suffix.lower() in extensions)
        results[d.name] = count
        total_images += count

results["_TOTAL_"] = total_images

with open("ai/scripts/anomaly_counts.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4)

print("SUCCESS: Counts written to ai/scripts/anomaly_counts.json")
