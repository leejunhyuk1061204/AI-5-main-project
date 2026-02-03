import os
import re

def extract_targets(file_path, encoding='utf-8'):
    targets = set()
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            content = f.read()
            # Look for ("Brand", "Year", "Model") pattern
            matches = re.findall(r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', content)
            for m in matches:
                targets.add(m)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return targets

all_targets = set()
all_targets.update(extract_targets('scripts/download_bulk_manuals.py'))
all_targets.update(extract_targets('scripts/extra_targets.txt', encoding='utf-16le'))
all_targets.update(extract_targets('scripts/extra_targets_v2_utf8.txt', encoding='utf-8'))
all_targets.update(extract_targets('scripts/extra_targets_v3_utf8.txt', encoding='utf-8'))

print(f"Total Unique Targets Found: {len(all_targets)}")

# Check against parsed files
parsed_dir = "data/manuals/parsed"
parsed_files = {f.replace('_full.json', '') for f in os.listdir(parsed_dir) if f.endswith('.json')}

remaining = []
for b, y, m in sorted(list(all_targets)):
    key = f"{b}_{y}_{m.replace('%20', '_')}"
    if key not in parsed_files:
        remaining.append((b, y, m))

print(f"Remaining (Not Parsed): {len(remaining)}")

# Group by brand for a summary
brand_counts = {}
for b, y, m in remaining:
    brand_counts[b] = brand_counts.get(b, 0) + 1

print("\nRemaining Brands:")
for b, c in sorted(brand_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"- {b}: {c}")

# Save the consolidated list for the new script
# We can just write it as a python list or a json.
import json
with open('data/manuals/consolidated_targets.json', 'w', encoding='utf-8') as f:
    json.dump(remaining, f, ensure_ascii=False, indent=2)
