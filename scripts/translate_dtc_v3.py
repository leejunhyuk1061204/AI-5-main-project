import json
import os
import time
import re
import hashlib
import sys
import sqlite3

# 자동차 전문 용어 사전 import
from automotive_terms import AUTOMOTIVE_TERMS

# --- 설정 ---
INPUT_FILES = {
    "bulk": "data/dtc/github_dtc_bulk.json",
    "summary": "data/dtc/batch_dtc_summary.json",
    "sample": "data/dtc/dry_run_sample.json",
    "db": "data/dtc/github_dtc_codes.db"
}

SEED_FILE = "db/seed_dtc.sql"

# Windows 한글 깨짐 방지
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def translate(text):
    """용어 사전으로 영어 → 한글 치환 (LLM 없이)"""
    if not text:
        return ""
    
    result = text
    
    # 긴 구문부터 치환 (순서 중요!)
    sorted_terms = sorted(AUTOMOTIVE_TERMS.items(), key=lambda x: len(x[0]), reverse=True)
    
    for en, ko in sorted_terms:
        # 대소문자 무시하고 치환 (Word Boundary 적용하여 부분 일치 방지)
        # 예: "AC"가 "Contact"의 중간을 치환하지 않도록 \b 사용
        pattern = re.compile(r'(?<![a-zA-Z])' + re.escape(en) + r'(?![a-zA-Z])', re.IGNORECASE)
        result = pattern.sub(ko, result)
    
    return result.strip()

def generate_sql(category, content, metadata):
    """SQL INSERT 생성"""
    def escape(s):
        if s is None: return "NULL"
        return "'" + str(s).replace("'", "''") + "'"
    
    content_hash = get_hash(content)
    meta_json = json.dumps(metadata, ensure_ascii=False)
    
    return f"INSERT INTO knowledge_vectors (category, content, metadata, content_hash) " \
           f"VALUES ({escape(category)}, {escape(content)}, {escape(meta_json)}, {escape(content_hash)}) " \
           f"ON CONFLICT (content_hash) DO NOTHING;\n"

def process_json_file(file_key, sql_f, limit=None):
    """JSON 파일 처리 (Bulk, Summary, Sample)"""
    file_path = INPUT_FILES.get(file_key)
    if not file_path or not os.path.exists(file_path):
        print(f"  {file_key} file not found: {file_path}")
        return 0
    
    print(f"Loading {file_key} data...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 데이터가 리스트가 아닌 경우(dict 등) 처리
    if isinstance(data, dict):
        # sample이나 summary가 dict 구조일 수 있음 (확인 필요하지만 일단 리스트로 가정하거나 처리)
        # 기존 로직 참고: bulk는 리스트. summary/sample은 구조 확인 필요.
        # 대부분 리스트임.
        pass

    items = data if isinstance(data, list) else []
    total = len(items) if limit is None else min(limit, len(items))
    print(f"Processing {total} of {len(items)} items from {file_key}...")
    
    count = 0
    for i, item in enumerate(items[:total]):
        # 필드명이 조금씩 다를 수 있음
        original = item.get('original_context') or item.get('title') or item.get('description', '')
        code = item.get('code') or item.get('dtc_code', 'UNKNOWN')
        
        translated = translate(original)
        
        content = f"[{code}] {translated}"
        metadata = {
            "original_en": original,
            "manufacturer": item.get('metadata', {}).get('manufacturer', 'Unknown'),
            "dtc_code": code,
            "source": f"github_dtc_{file_key}"
        }
        sql_f.write(generate_sql("DTC_GUIDE", content, metadata))
        count += 1
        
        if (i + 1) % 1000 == 0:
            print(f"  Processed {i + 1}/{total}...")
    
    return count

def process_sqlite(sql_f, limit=None):
    """SQLite DB 처리"""
    db_path = INPUT_FILES["db"]
    if not os.path.exists(db_path):
        print(f"  DB file not found: {db_path}")
        return 0
        
    print(f"Loading SQLite data from {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # p_codes 테이블 조회 (예시)
    try:
        cursor.execute("SELECT count(*) FROM dtc_definitions")
        total_rows = cursor.fetchone()[0]
        target_rows = total_rows if limit is None else min(limit, total_rows)
        
        print(f"Processing {target_rows} of {total_rows} rows from SQLite...")
        
        query = "SELECT code, description, manufacturer FROM dtc_definitions"
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        
        count = 0
        for row in cursor.fetchall():
            code, description, manufacturer = row
            if not description: continue
            
            translated = translate(description)
            
            content = f"[{code}] {translated}"
            metadata = {
                "original_en": description,
                "manufacturer": manufacturer or 'Unknown',
                "dtc_code": code,
                "type": "P",
                "is_generic": False,
                "source": "github_dtc_codes.db"
            }

            sql_f.write(generate_sql("DTC_GUIDE", content, metadata))
            count += 1
            
            if (count) % 1000 == 0:
                print(f"  Processed {count}/{target_rows}...")
                
        return count
        
    except Exception as e:
        print(f"  SQLite Error: {e}")
        return 0
    finally:
        conn.close()

def main():
    print("=== DTC Translation (Dictionary-based, No LLM) ===\n")
    
    os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, 'w', encoding='utf-8') as f:
        f.write("-- DTC Knowledge Base Seed Data\n")
        f.write(f"-- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"-- Translation: Dictionary-based ({len(AUTOMOTIVE_TERMS)} terms)\n\n")
        
        total_count = 0
        
        # 1. Bulk Data
        total_count += process_json_file("bulk", f)
        
        # 2. Summary Data
        total_count += process_json_file("summary", f)
        
        # 3. Sample Data
        total_count += process_json_file("sample", f)
        
        # 4. SQLite DB
        total_count += process_sqlite(f)
    
    print(f"\nDone! Total {total_count} records saved to {SEED_FILE}")

if __name__ == "__main__":
    main()
