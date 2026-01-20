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

# 중간 저장 및 결과 파일
KO_FILE = "data/dtc/github_dtc_bulk_ko.json"
SEED_FILE = "db/seed_dtc.sql"

# Ollama 설정
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"
BATCH_SIZE = 20  # Bulk용 (용어 사전 포함으로 배치 사이즈 축소)

# Windows 한글 깨짐 방지를 위한 출력 설정
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

# 용어 사전을 프롬프트용 문자열로 변환 (상위 100개 핵심 용어)
TERMS_FOR_PROMPT = "\n".join([
    f"- {en} = {ko}" 
    for en, ko in list(AUTOMOTIVE_TERMS.items())[:100]
])

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# 후처리용 오역 수정 사전 (LLM이 자주 틀리는 것들)
POST_PROCESS_FIXES = {
    # Misfire 관련
    "미사일": "실화",
    "미스피시": "실화",
    "미스파이어": "실화",
    # Cylinder 관련
    "캔터스": "실린더",
    "캘시앙": "실린더",
    "침상": "실린더",
    "터보": "실린더",  # "터보 미스피시" -> "실린더 실화"
    # Throttle 관련
    "조차": "스로틀",
    # BARO 관련
    "바오": "대기압",
    "바르로": "대기압",
    "바르오": "대기압",  # 추가
    # Circuit 관련
    "케이트": "회로",
    "셀": "회로",
    # Accelerator 관련
    "가속 주위": "가속 페달 위치",  # Accelerator Position
    # 기타 오역
    "센터라인": "산소 센서",  # HO2S11
    "레이블": "라벨",
    "단단장식": "닫힌",  # Closed
}

def clean_korean(text):
    """LLM 번역 후처리 - 오역 강제 수정"""
    if not text: return ""
    
    # 기존 깨진 한글 수정
    text = text.replace("저舷", "희박")
    
    # 오역 후처리
    for wrong, correct in POST_PROCESS_FIXES.items():
        text = text.replace(wrong, correct)
    
    return text.strip()


def translate_batch(texts, is_summary=False):
    """용어 사전을 포함한 Ollama 번역"""
    if not texts: return {}
    
    # 프롬프트에 용어 사전 포함
    terms_header = f"""[Automotive DTC Translation Dictionary - MUST use these exact Korean terms:]
{TERMS_FOR_PROMPT}

[IMPORTANT RULES:]
1. Use the dictionary above for ALL technical terms
2. Cylinder = 실린더 (NOT 캘시앙/침상/터보)
3. Misfire = 실화 (NOT 미사일/미스피시)
4. Throttle = 스로틀 (NOT 조차)
5. BARO = 대기압 센서 (NOT 바오)
6. Circuit = 회로 (NOT 케이트)
7. Keep Bank 1, Bank 2 as 뱅크 1, 뱅크 2

"""
    
    if is_summary:
        # 긴 텍스트는 하나씩 처리
        combined_input = texts[0]
        prompt = f"""{terms_header}[Task: Translate this automotive technical document into Korean. Keep Markdown headers. Output only Korean translation:]

{combined_input}"""
    else:
        combined_input = "\n".join([f"[{i}] {text}" for i, text in enumerate(texts)])
        prompt = f"""{terms_header}[Task: Translate these DTC descriptions into concise Korean. Format output as: [index] Korean translation]

{combined_input}"""


    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=120
        )
        if response.status_code == 200:
            result_text = response.json().get('response', '')
            
            translated_lines = {}
            if is_summary:
                translated_lines[0] = result_text.strip()
            else:
                lines = result_text.split('\n')
                for line in lines:
                    match = re.search(r'\[?(\d+)\]?[\s\.\:]+(.*)', line)
                    if match:
                        idx = int(match.group(1))
                        content = clean_korean(match.group(2))
                        translated_lines[idx] = content
            return translated_lines
    except Exception as e:
        print(f"  [Error] {e}")
    return {}

def generate_sql_statement(category, content, metadata):
    """INSERT SQL 생성 (PostgreSQL escape 처리)"""
    def escape(s):
        if s is None: return "NULL"
        return "'" + str(s).replace("'", "''") + "'"

    content_hash = get_hash(content)
    meta_json = json.dumps(metadata, ensure_ascii=False)
    
    sql = f"INSERT INTO knowledge_vectors (category, content, metadata, content_hash) " \
          f"VALUES ({escape(category)}, {escape(content)}, {escape(meta_json)}, {escape(content_hash)}) " \
          f"ON CONFLICT (content_hash) DO NOTHING;\n"
    return sql

def process_bulk(processed_data):
    """github_dtc_bulk.json 처리"""
    if not os.path.exists(INPUT_FILES["bulk"]): return
    
    with open(INPUT_FILES["bulk"], 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 이미 번역된 해시 맵핑
    processed_hashes = {get_hash(it.get('original_context','')): it for it in processed_data if it.get('korean_description')}
    
    print(f"Processing Bulk DTC ({len(data)} items)...")
    
    new_results = []
    with open(SEED_FILE, 'a', encoding='utf-8') as sql_f:
        for i in range(0, len(data), BATCH_SIZE):
            if i >= BATCH_SIZE * 3: break # 검증용: 3개 배치만 처리
            batch = data[i : i + BATCH_SIZE]
            to_translate = []
            batch_indices = []
            
            for j, item in enumerate(batch):
                h = get_hash(item['original_context'])
                if h in processed_hashes:
                    # 기존 번역 활용 (깨짐 수정 포함)
                    item['korean_description'] = clean_korean(processed_hashes[h]['korean_description'])
                else:
                    to_translate.append(item['original_context'])
                    batch_indices.append(j)
            
            if to_translate:
                print(f"  Translating batch {i//BATCH_SIZE + 1}...")
                translations = translate_batch(to_translate)
                for tidx, bidx in enumerate(batch_indices):
                    batch[bidx]['korean_description'] = translations.get(tidx, "")
            
            for item in batch:
                if item.get('korean_description'):
                    content = f"[{item['code']}] {item['korean_description']}"
                    metadata = {
                        "original_en": item['original_context'],
                        "manufacturer": item.get('metadata', {}).get('manufacturer', 'GENERIC'),
                        "dtc_code": item['code'],
                        "source": "github_dtc_bulk"
                    }
                    sql_f.write(generate_sql_statement("DTC_GUIDE", content, metadata))
                    new_results.append(item)
            
            # 진행 상황 저장
            if i % 1000 == 0:
                with open(KO_FILE, 'w', encoding='utf-8') as f:
                    json.dump(new_results, f, ensure_ascii=False, indent=2)

def process_summary_and_sample():
    """batch_dtc_summary.json 및 dry_run_sample.json 처리 (긴 텍스트)"""
    for key in ["summary", "sample"]:
        path = INPUT_FILES[key]
        if not os.path.exists(path): continue
        
        print(f"Processing {key} (Long Text)...")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        items = data if isinstance(data, list) else [data]
        
        with open(SEED_FILE, 'a', encoding='utf-8') as sql_f:
            for item in items[:1]: # 검증용: 1개만 처리
                title = item.get('title', 'Unknown Title')
                context = item.get('original_context', '')
                
                print(f"  Translating {title[:30]}...")
                # 제목 번역
                t_title_res = translate_batch([title])
                ko_title = t_title_res.get(0, title)
                
                # 본문 섹션화 및 번역
                sections = re.split(r'(### .*\n)', context)
                translated_sections = []
                for sec in sections:
                    if not sec.strip(): continue
                    if sec.startswith('### '):
                        translated_sections.append(sec) # 헤더는 유지
                    else:
                        t_sec_res = translate_batch([sec], is_summary=True)
                        translated_sections.append(t_sec_res.get(0, sec))
                
                ko_context = "".join(translated_sections)
                content = f"### {ko_title}\n\n{ko_context}"
                metadata = {
                    "original_title": title,
                    "dtc_code": item.get('code', 'N/A'),
                    "source": os.path.basename(path)
                }
                sql_f.write(generate_sql_statement("DTC_GUIDE", content, metadata))

def process_sqlite():
    """github_dtc_codes.db 처리"""
    if not os.path.exists(INPUT_FILES["db"]): return
    
    print("Processing SQLite DB...")
    try:
        conn = sqlite3.connect(INPUT_FILES["db"])
        cursor = conn.cursor()
        cursor.execute("SELECT code, manufacturer, description, type, is_generic FROM dtc_definitions")
        rows = cursor.fetchall()
        
        with open(SEED_FILE, 'a', encoding='utf-8') as sql_f:
            # 배치로 번역
            for i in range(0, len(rows), BATCH_SIZE):
                if i >= BATCH_SIZE * 2: break # 검증용: 2개 배치만 처리
                batch = rows[i : i + BATCH_SIZE]
                texts = [r[2] for r in batch]
                print(f"  Translating DB batch {i//BATCH_SIZE + 1}...")
                translations = translate_batch(texts)
                
                for j, row in enumerate(batch):
                    ko_desc = translations.get(j, "")
                    if ko_desc:
                        content = f"[{row[0]}] {ko_desc}"
                        metadata = {
                            "original_en": row[2],
                            "manufacturer": row[1],
                            "dtc_code": row[0],
                            "type": row[3],
                            "is_generic": bool(row[4]),
                            "source": "github_dtc_codes.db"
                        }
                        sql_f.write(generate_sql_statement("DTC_GUIDE", content, metadata))
        conn.close()
    except Exception as e:
        print(f"  [SQLite Error] {e}")

def main():
    print("Starting DTC Translation & SQL Generation...")
    
    # 0. SQL 파일 초기화
    if not os.path.exists(os.path.dirname(SEED_FILE)):
        os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, 'w', encoding='utf-8') as f:
        f.write("-- DTC Knowledge Base Seed Data\n")
        f.write("-- Generated at: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n\n")

    # 1. 기존 번역 데이터 로드 (캐시 역할)
    processed_data = []
    if os.path.exists(KO_FILE):
        with open(KO_FILE, 'r', encoding='utf-8') as f:
            try: processed_data = json.load(f)
            except: pass

    # 2. 각 소스별 처리
    process_bulk(processed_data)
    process_summary_and_sample()
    process_sqlite()

    print(f"\nFinished! Results saved to {SEED_FILE}")

if __name__ == "__main__":
    main()
