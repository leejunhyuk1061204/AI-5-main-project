import os
import sqlite3
import json
import time

# --- 헌법 준수 (Safety Guardrails) ---
LOCAL_DB_PATH = "data/dtc/github_dtc_codes.db"
OUTPUT_JSON_PATH = "data/dtc/github_dtc_bulk.json"
# -----------------------------------

def convert_to_json():
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"DB not found at {LOCAL_DB_PATH}")
        return
    
    print("Converting 28,220+ codes to JSON...")
    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 분석된 테이블 이름: dtc_definitions
        cursor.execute("SELECT code, manufacturer, description, type, is_generic FROM dtc_definitions")
        rows = cursor.fetchall()
        
        bulk_data = []
        for row in rows:
            bulk_data.append({
                "code": row[0],
                "category": "DTC_DEFINITION",
                "metadata": {
                    "manufacturer": row[1],
                    "type": row[3],
                    "is_generic": bool(row[4])
                },
                "original_context": row[2],
                "source_url": "https://github.com/Wal33D/dtc-database",
                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(bulk_data, f, indent=4, ensure_ascii=False)
            
        print(f"Successfully integrated {len(bulk_data)} codes into a single JSON.")
    except Exception as e:
        print(f"Error during conversion: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    convert_to_json()
