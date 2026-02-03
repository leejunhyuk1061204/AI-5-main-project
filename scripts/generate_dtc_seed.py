import json
import os

def generate_sql_seed():
    json_path = os.path.join("data", "dtc", "github_dtc_bulk_translated.json")
    output_path = os.path.join("db", "seed_dtc_data.sql")
    
    print(f"Reading JSON from {json_path}...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {json_path}")
        return

    print(f"Found {len(data)} entries. Generating SQL...")

    # Load Term Dictionary for Post-processing
    try:
        from automotive_terms import AUTOMOTIVE_TERMS
        print(f"Loaded {len(AUTOMOTIVE_TERMS)} terms for post-processing cleanup.")
    except ImportError:
        print("Warning: automotive_terms.py not found. Skipping post-processing.")
        AUTOMOTIVE_TERMS = {}

    with open(output_path, 'w', encoding='utf-8') as f:
        # 1. Create Table
        f.write("-- DTC Code Definitions Table (Korean Optimized)\n")
        f.write("CREATE TABLE IF NOT EXISTS dtc_codes (\n")
        f.write("    code VARCHAR(20) NOT NULL,\n")
        f.write("    manufacturer VARCHAR(50) DEFAULT 'GENERIC',\n")
        f.write("    description_ko TEXT,\n")
        f.write("    summary_ko VARCHAR(255),\n")
        f.write("    tts_phrase TEXT,\n")
        f.write("    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n")
        f.write("    PRIMARY KEY (code, manufacturer)\n")
        f.write(");\n\n")

        # 2. Insert Data
        f.write("INSERT INTO dtc_codes (code, manufacturer, description_ko, summary_ko, tts_phrase) VALUES\n")
        
        batch_size = 1000
        buffer = []
        
        for i, item in enumerate(data):
            code = item.get('code', '').replace("'", "''")
            
            # Extract manufacturer from metadata
            manufacturer = 'GENERIC'
            if 'metadata' in item and 'manufacturer' in item['metadata']:
                manufacturer = item['metadata']['manufacturer']
                if not manufacturer:
                    manufacturer = 'GENERIC'
            manufacturer = manufacturer.replace("'", "''")

            desc_ko = item.get('korean_translation', '')
            summary_ko = item.get('summary_ko', '')
            tts = item.get('tts_phrase', '')

            # [AUTO-FIX] Apply Dictionary Replacements to improve quality
            if AUTOMOTIVE_TERMS:
                for bad_term, good_term in AUTOMOTIVE_TERMS.items():
                    # Check if 'bad_term' (Korean value in dict?)
                    # No, the dictionary is EnglishKey -> KoreanValue.
                    # Use Reverse Map or just specific manual fixes if needed?
                    # Actually user hated "시프트 솔레노이드" (value) -> shift solenoid (key).
                    # The dictionary was: "Shift Solenoid": "시프트 솔레노이드" (Old)
                    # We changed it to: "Shift Solenoid": "변속 솔레노이드" (New)
                    # But the JSON data might already contain "시프트 솔레노이드".
                    # So we need to replace "시프트 솔레노이드" -> "변속 솔레노이드".
                    pass
            
            # Manual Critical Fixes (based on user feedback)
            # These replace the transliterated garbage with proper terms
            replacements = {
                "시프트 솔레노이드": "변속 솔레노이드",
                "하이드라우릭": "유압",
                "서킷": "회로",
                "오픈": "단선",
                "쇼트": "단락",
                "로 우": "낮음",
                "하 이": "높음",
                "인풋": "입력",
                "아웃풋": "출력",
                "트랜스미션": "변속기",
                "일렉트리컬": "전기",
                "에미션": "배출가스",
                "캠샤프트": "캠축",
                "크랭크샤프트": "크랭크축",
                "Bank 1": "뱅크 1", # Spacing fix
                "Bank 2": "뱅크 2"
            }
            
            for bad, good in replacements.items():
                desc_ko = desc_ko.replace(bad, good)
                tts = tts.replace(bad, good)
                summary_ko = summary_ko.replace(bad, good)

            # Validating and Escaping for SQL
            desc_ko = desc_ko.replace("'", "''")
            summary_ko = summary_ko.replace("'", "''")
            tts = tts.replace("'", "''")

            # Validate essential fields
            if not code:
                continue

            value_str = f"('{code}', '{manufacturer}', '{desc_ko}', '{summary_ko}', '{tts}')"
            buffer.append(value_str)

            if len(buffer) >= batch_size:
                f.write(",\n".join(buffer))
                f.write("\nON CONFLICT (code, manufacturer) DO UPDATE SET\n")
                f.write("    description_ko = EXCLUDED.description_ko,\n")
                f.write("    summary_ko = EXCLUDED.summary_ko,\n")
                f.write("    tts_phrase = EXCLUDED.tts_phrase;\n\n")
                
                if i < len(data) - 1: # If not the very last batch ever
                    f.write("INSERT INTO dtc_codes (code, manufacturer, description_ko, summary_ko, tts_phrase) VALUES\n")
                buffer = []
        
        # Write remaining buffer
        if buffer:
            f.write(",\n".join(buffer))
            f.write("\nON CONFLICT (code, manufacturer) DO UPDATE SET\n")
            f.write("    description_ko = EXCLUDED.description_ko,\n")
            f.write("    summary_ko = EXCLUDED.summary_ko,\n")
            f.write("    tts_phrase = EXCLUDED.tts_phrase;\n")

    print(f"Successfully wrote SQL to {output_path}")

if __name__ == "__main__":
    generate_sql_seed()
