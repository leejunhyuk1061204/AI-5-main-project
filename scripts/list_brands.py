import json
import os

path = "data/manuals/charmli_hierarchy_map.json"

if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        keys = list(data.keys())
        keys.sort()
        print("Available Brands:")
        print(", ".join(keys))
else:
    print(f"File not found: {path}")
