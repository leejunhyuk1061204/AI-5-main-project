import os
import collections

parsed_dir = "data/manuals/parsed"
files = [f for f in os.listdir(parsed_dir) if f.endswith("_full.json")]

print(f"Total Files: {len(files)}")

brands = collections.defaultdict(int)
models = collections.defaultdict(int)
unique_models = set()

for f in files:
    # Filename format: Brand_Year_Model_full.json
    # parsing logic depends on underscores. 
    # But model names themselves might have underscores if they had spaces.
    # We know the suffix is "_full.json"
    
    name_part = f.replace("_full.json", "")
    parts = name_part.split('_')
    
    # Heuristic: First part is Brand, Second is Year. Rest is Model.
    if len(parts) >= 3:
        brand = parts[0]
        year = parts[1]
        model_parts = parts[2:]
        model = " ".join(model_parts)
        
        brands[brand] += 1
        
        # specific year-model compbination
        models[f"{brand} {model}"] += 1
        
        # distinctive model name (ignoring year)
        unique_models.add(f"{brand} {model} ({year})")

print("\n=== Brand Breakdown ===")
for b, count in sorted(brands.items(), key=lambda x: x[1], reverse=True):
    print(f"- {b}: {count}")

# print("\n=== Sample Models ===")
# for m in list(unique_models)[:10]:
#     print(m)
