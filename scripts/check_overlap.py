import json
import os

def load_codes(file_path, file_type):
    codes = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if file_type == 'list':
            for item in data:
                if 'code' in item:
                    codes.add(item['code'])
        elif file_type == 'dict':
            for key, value in data.items():
                if 'code' in value:
                    codes.add(value['code'])
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return codes

base_path = 'data/dtc/translated'
file1 = 'batch_dtc_summary_translated.json'
file2 = 'github_dtc_bulk_translated.json'
file3 = 'translated_dtc_final.json'

path1 = os.path.join(base_path, file1)
path2 = os.path.join(base_path, file2)
path3 = os.path.join(base_path, file3)

print("Loading files...")
codes1 = load_codes(path1, 'list')
print(f"{file1}: {len(codes1)} codes")

codes2 = load_codes(path2, 'list')
print(f"{file2}: {len(codes2)} codes")

codes3 = load_codes(path3, 'dict')
print(f"{file3}: {len(codes3)} codes")

print("\nChecking overlaps...")

overlap12 = codes1.intersection(codes2)
overlap13 = codes1.intersection(codes3)
overlap23 = codes2.intersection(codes3)
overlap_all = codes1.intersection(codes2).intersection(codes3)

print(f"Overlap {file1} & {file2}: {len(overlap12)}")
if overlap12:
    print(f"  Examples: {list(overlap12)[:5]}")

print(f"Overlap {file1} & {file3}: {len(overlap13)}")
if overlap13:
    print(f"  Examples: {list(overlap13)[:5]}")

print(f"Overlap {file2} & {file3}: {len(overlap23)}")
if overlap23:
    print(f"  Examples: {list(overlap23)[:5]}")

print(f"Overlap ALL 3: {len(overlap_all)}")
