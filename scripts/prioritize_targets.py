import json

input_path = "data/manuals/potential_new_targets.json"
output_path = "data/manuals/prioritized_targets.json"

with open(input_path, "r", encoding="utf-8") as f:
    targets = json.load(f)

# Group by year
year_priority = {
    "2013": 1,
    "2012": 2,
    "2011": 3,
    "2010": 4
}

# Sort: Priority Year first, then by Brand/Model
sorted_targets = sorted(targets, key=lambda x: (year_priority.get(x["year"], 99), x["brand"], x["model"]))

with open(output_path, "w", encoding="utf-8") as f:
    json.dump([[t["brand"], t["year"], t["model"]] for t in sorted_targets], f, ensure_ascii=False, indent=2)

print(f"Prioritization Complete.")
print(f"Total Targets: {len(sorted_targets)}")
print(f"2013 Models: {len([t for t in sorted_targets if t['year'] == '2013'])}")
print(f"Saved to {output_path}")
