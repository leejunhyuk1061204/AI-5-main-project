import json
import os

TARGET_LIST_PATH = r"C:\Users\301\dev\AI-5-main-project\data\manuals\all_discovered_targets.json"
OUTPUT_DIR = r"G:\내 드라이브\정비지침서\원본_zip"

def main():
    if not os.path.exists(TARGET_LIST_PATH):
        print(f"File not found: {TARGET_LIST_PATH}")
        return

    with open(TARGET_LIST_PATH, 'r', encoding='utf-8') as f:
        try:
            targets = json.load(f)
        except Exception as e:
            print(f"Failed to load JSON: {e}")
            return

    print(f"Total targets in JSON: {len(targets)}")

    expected_filenames = set()
    for item in targets:
        if isinstance(item, dict):
            brand, year, model = item['brand'], item['year'], item['model']
        elif isinstance(item, list) and len(item) == 3:
            brand, year, model = item
        else:
            continue
            
        filename = f"{brand}_{year}_{model.replace('%20', '_')}.zip"
        expected_filenames.add(filename)

    print(f"Expected unique files: {len(expected_filenames)}")

    if not os.path.exists(OUTPUT_DIR):
        print(f"Directory not found: {OUTPUT_DIR}")
        return

    actual_files = set(os.listdir(OUTPUT_DIR))
    print(f"Actual files in directory: {len(actual_files)}")

    missing_files = expected_filenames - actual_files
    print(f"Missing files count: {len(missing_files)}")

    if missing_files:
        print("\nLast 10 missing files:")
        for f in sorted(list(missing_files))[-10:]:
            print(f)
            
        with open("missing_files_list.txt", "w", encoding="utf-8") as mf:
            for f in sorted(list(missing_files)):
                mf.write(f + "\n")
        print("\nSaved missing files list to 'missing_files_list.txt'")

if __name__ == "__main__":
    main()
