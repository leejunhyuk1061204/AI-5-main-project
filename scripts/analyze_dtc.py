import json
import os

base_path = r'data/dtc/translated'
files = {
    'bulk': 'github_dtc_bulk_translated.json',
    'summary': 'batch_dtc_summary_translated.json',
    'final': 'translated_dtc_final.json'
}

def load_json(name):
    path = os.path.join(base_path, files[name])
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

bulk_data = load_json('bulk')
summary_data = load_json('summary')
final_data = load_json('final')

# Extract codes and content
# Bulk: list of objects
bulk_dict = {} # (code, manufacturer) -> content
for item in bulk_data:
    code = item.get('code')
    mfr = item.get('metadata', {}).get('manufacturer', 'GENERIC')
    bulk_dict[(code, mfr)] = item.get('korean_translation')

# Summary: list of objects
summary_dict = {} # code -> content
for item in summary_data:
    summary_dict[item.get('code')] = item.get('korean_translation')

# Final: dict of Code_Description -> Object
final_map = {} # code -> content
for key, obj in final_data.items():
    code = obj.get('code')
    final_map[code] = obj.get('translated')

print(f"Counts: Bulk={len(bulk_dict)}, Summary={len(summary_dict)}, Final={len(final_map)}")

# 1. Bulk vs Final
bulk_codes = set(c for c, m in bulk_dict.keys())
final_codes = set(final_map.keys())

overlap_bf = bulk_codes.intersection(final_codes)
only_bulk = bulk_codes - final_codes
only_final = final_codes - bulk_codes

print(f"\nBulk vs Final:")
print(f"  Overlap codes: {len(overlap_bf)}")
print(f"  Only in Bulk: {len(only_bulk)}")
print(f"  Only in Final: {len(only_final)}")

# 2. Bulk vs Summary
summary_codes = set(summary_dict.keys())
overlap_bs = bulk_codes.intersection(summary_codes)
print(f"\nBulk vs Summary:")
print(f"  Overlap codes: {len(overlap_bs)}")
print(f"  Example overlaps: {list(overlap_bs)[:5]}")

# 3. Content Check for P0101 (if exists in all)
test_code = 'P0101'
print(f"\nContent check for {test_code}:")
if test_code in bulk_codes:
    # Find all variants in bulk (different manufacturers might have different definitions)
    variants = [val for (c, m), val in bulk_dict.items() if c == test_code]
    print(f"  Bulk variants ({len(variants)}): {variants[0][:50]}...")
if test_code in summary_dict:
    print(f"  Summary: {summary_dict[test_code][:50]}...")
if test_code in final_map:
    print(f"  Final: {final_map[test_code][:50]}...")

# 4. Check if Final is a perfect subset of Bulk
# (Assuming Final maps to one of the bulk entries)
match_count = 0
for code in overlap_bf:
    final_text = final_map[code]
    # Check if this text exists in any bulk variant for this code
    bulk_variants = [val for (c, m), val in bulk_dict.items() if c == code]
    if any(final_text == v for v in bulk_variants):
        match_count += 1

print(f"\nFinal content vs Bulk content:")
print(f"  Final items matching a Bulk variant: {match_count} / {len(overlap_bf)}")
