import json
import os

KO_FILE = "data/dtc/github_dtc_bulk_ko.json"

def check_status():
    if not os.path.exists(KO_FILE):
        print("File not found.")
        return

    with open(KO_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    translated = sum(1 for item in data if item.get('korean_description', '').strip())
    empty = total - translated

    print(f"Total entries: {total}")
    print(f"Translated: {translated}")
    print(f"Empty: {empty}")
    
    if empty > 0:
        print("\nSample empty entries:")
        count = 0
        for i, item in enumerate(data):
            if not item.get('korean_description', '').strip():
                print(f"Index {i}: {item.get('code')} - {item.get('original_context')}")
                count += 1
                if count >= 5: break

if __name__ == "__main__":
    check_status()
