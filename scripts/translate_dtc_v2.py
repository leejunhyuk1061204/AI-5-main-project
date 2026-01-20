import json
import requests
import os
import time
import re
import sqlite3
import hashlib
import sys

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

# Ollama 설정
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"
BATCH_SIZE = 20

# Windows 한글 깨짐 방지
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def pre_translate(text):
    """1단계: 용어 사전으로 영어 → 한글 치환"""
    if not text:
        return ""
    
    result = text
    
    # 긴 구문부터 치환 (순서 중요)
    sorted_terms = sorted(AUTOMOTIVE_TERMS.items(), key=lambda x: len(x[0]), reverse=True)
    
    for en, ko in sorted_terms:
        # 대소문자 무시하고 치환
        pattern = re.compile(re.escape(en), re.IGNORECASE)
        result = pattern.sub(ko, result)
    
    return result

def refine_with_llm(texts):
    """2단계: LLM으로 문장 자연스럽게 다듬기"""
    if not texts:
        return {}
    
    combined = "\n".join([f"[{i}] {t}" for i, t in enumerate(texts)])
    
    prompt = f"""아래는 자동차 DTC 코드 설명을 단어 단위로 한글 치환한 것입니다.
문장이 어색할 수 있으니 자연스러운 한국어로 다듬어주세요.
단, 기술 용어는 그대로 유지하세요.
형식: [숫자] 다듬은 문장

{combined}"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=120
        )
        if response.status_code == 200:
            result_text = response.json().get('response', '')
            
            translated_lines = {}
            for line in result_text.split('\n'):
                match = re.search(r'\[?(\d+)\]?[\s\.\:]+(.*)', line)
                if match:
                    idx = int(match.group(1))
                    content = match.group(2).strip()
                    translated_lines[idx] = content
            return translated_lines
    except Exception as e:
        print(f"  [LLM Error] {e}")
    
    # LLM 실패 시 원본 반환
    return {i: t for i, t in enumerate(texts)}

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

def process_bulk():
    """Bulk DTC 처리"""
    if not os.path.exists(INPUT_FILES["bulk"]):
        return
    
    print("Loading bulk DTC data...")
    with open(INPUT_FILES["bulk"], 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Processing {len(data)} items...")
    
    with open(SEED_FILE, 'a', encoding='utf-8') as sql_f:
        for i in range(0, len(data), BATCH_SIZE):
            if i >= BATCH_SIZE * 3:  # 테스트: 3배치만
                break
                
            batch = data[i : i + BATCH_SIZE]
            
            # 1단계: 용어 치환
            pre_translated = [pre_translate(item.get('original_context', '')) for item in batch]
            
            print(f"  Batch {i//BATCH_SIZE + 1}: Pre-translated samples:")
            for j in range(min(3, len(pre_translated))):
                print(f"    {batch[j].get('code')}: {pre_translated[j][:50]}...")
            
            # 2단계: LLM 다듬기
            refined = refine_with_llm(pre_translated)
            
            # 3단계: SQL 생성
            for j, item in enumerate(batch):
                ko_text = refined.get(j, pre_translated[j])
                content = f"[{item.get('code')}] {ko_text}"
                metadata = {
                    "original_en": item.get('original_context', ''),
                    "manufacturer": item.get('metadata', {}).get('manufacturer', 'Unknown'),
                    "dtc_code": item.get('code'),
                    "source": "github_dtc_bulk"
                }
                sql_f.write(generate_sql("DTC_GUIDE", content, metadata))
            
            print(f"  Batch {i//BATCH_SIZE + 1} done")
            time.sleep(0.5)

def main():
    print("=== DTC Translation (Pre-translate + LLM Refine) ===\n")
    
    # SQL 파일 초기화
    os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, 'w', encoding='utf-8') as f:
        f.write("-- DTC Knowledge Base Seed Data\n")
        f.write(f"-- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    process_bulk()
    
    print(f"\nDone! Results saved to {SEED_FILE}")

if __name__ == "__main__":
    main()
