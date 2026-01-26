import json
import os
import sqlite3
import asyncio
import aiohttp
import sys
from tqdm import tqdm
from automotive_terms import AUTOMOTIVE_TERMS

# 한글 주석: DTC 데이터를 통합 로드하여 Ollama Qwen2.5를 통해 고품질 한글 번역 및 TTS 문구를 생성하는 스크립트입니다.

# --- 설정 (Configuration) ---
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHECK_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5:14b"  # 32B(20GB+)는 4090(24GB)에서 메모리 스왑으로 느려짐. 14B가 최적(속도 5배 이상)
BATCH_SIZE = 30  # 14B 모델은 가벼우므로 배치 30개도 충분히 소화 가능

# 스크립트 실행 위치 기준 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

DATA_SOURCES = {
    # runpod/data 폴더 구조에 맞춤 (data/파일명)
    "bulk": os.path.join(DATA_DIR, "github_dtc_bulk.json"),
    "backup": os.path.join(DATA_DIR, "github_dtc_bulk_ko_backup.json"),
    "summary": os.path.join(DATA_DIR, "batch_dtc_summary.json"),
    "sample": os.path.join(DATA_DIR, "dry_run_sample.json"),
    "db": os.path.join(DATA_DIR, "github_dtc_codes.db")
}

CACHE_FILE = os.path.join(DATA_DIR, "translated_cache.json")
FINAL_FILE = os.path.join(DATA_DIR, "translated_dtc_final.json")

# --- 시스템 프롬프트 구성 (경량화) ---
def get_system_prompt():
    # 전체 용어 사전을 매번 넣으면 속도가 매우 느려지므로, 핵심 규칙만 전달
    return """너는 자동차 정비 전문가이자 TTS 성우야.
자동차 고장 코드(DTC) 설명을 '운전자가 듣기 편한 한글 구어체'로 번역하고, 요약해줘.

[규칙]
1. 'Circuit Low' -> '회로 전압 낮음', 'Bank 1' -> '뱅크 1' 등 전문 용어는 표준 자동차 용어로 번역.
2. **반드시 JSON 형식만 출력** (Markdown/설명 금지).

[출력 예시]
{
    "translated": "흡기 온도 센서 회로 전압 낮음",
    "tts_phrase": "흡기 온도 센서의 회로 전압이 낮습니다. 점검이 필요합니다.",
    "summary": "흡기 센서 전압 낮음"
}
"""

async def check_ollama_server():
    """Ollama 서버 연결 확인"""
    print(f"Connecting to Ollama at {OLLAMA_CHECK_URL}...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(OLLAMA_CHECK_URL, timeout=5) as response:
                if response.status == 200:
                    print("✅ Ollama server is ready.")
                    return True
                else:
                    print(f"❌ Ollama server responded with status {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Could not connect to Ollama: {e}")
            return False

async def translate_item(session, code, original, system_prompt):
    """Ollama API를 통해 단일 항목 번역 요청"""
    prompt = f"DTC 코드: {code}\n영문 원문: {original}\n\n위 내용을 규칙에 맞춰 번역해줘."
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_ctx": 1024  # 문맥 길이를 줄여서 VRAM 절약 -> 동시 처리(Parallel) 효율 극대화
        }
    }
    
    try:
        # 32B 모델 처리 시간을 고려해 타임아웃을 5분(300초)으로 대폭 늘림
        async with session.post(OLLAMA_URL, json=payload, timeout=300) as response:
            if response.status == 200:
                result = await response.json()
                return json.loads(result.get("response", "{}"))
            else:
                return None
    except Exception as e:
        print(f"\nError translating {code}: {e}")
        return None

def load_all_data():
    """모든 소스 파일에서 DTC 데이터를 통합 로드 (중복 제거)"""
    all_dtcs = {} # code_original_hash -> {code, original, category}
    
    # helper to process list or dict
    def process_items(source_key, category_type):
        path = DATA_SOURCES.get(source_key)
        if not path or not os.path.exists(path):
            return
            
        print(f"Loading {source_key} from {path}...")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            items = data if isinstance(data, list) else [data]
            for item in items:
                code = item.get('code', 'UNKNOWN')
                orig = item.get('original_context', '')
                # Skip if already translated properly (optional check, but we load everything here)
                if orig:
                    key = f"{code}_{orig}"
                    all_dtcs[key] = {"code": code, "original": orig, "category": category_type}
        except Exception as e:
            print(f"Error loading {source_key}: {e}")

    # 1. Bulk & Backup (Plain definitions)
    process_items("bulk", "DEFINITION")
    process_items("backup", "DEFINITION")

    # 2. Summary & Sample (Long context)
    process_items("summary", "SUMMARY")
    process_items("sample", "SUMMARY")

    # 3. SQLite DB
    if os.path.exists(DATA_SOURCES["db"]):
        try:
            conn = sqlite3.connect(DATA_SOURCES["db"])
            cursor = conn.cursor()
            cursor.execute("SELECT code, description FROM dtc_definitions")
            for code, desc in cursor.fetchall():
                if desc:
                    key = f"{code}_{desc}"
                    all_dtcs[key] = {"code": code, "original": desc, "category": "DB_DEFINITION"}
            conn.close()
        except Exception as e:
             print(f"⚠️ Warning: Error reading DB at {DATA_SOURCES['db']}: {e}")
    else:
        print(f"⚠️ Warning: DB not found at {DATA_SOURCES['db']}")

    return list(all_dtcs.values())

async def main():
    # 모델 확인은 이미 run.sh에서 ollama pull로 보장하려 하지만, 연결 확인 차원
    if not await check_ollama_server():
        print("❌ Please ensure Ollama is running (try 'ollama serve' or check logs).")
        return

    # 데이터 로드
    items = load_all_data()
    print(f"Total unique DTC items to translate: {len(items)}")

    if not items:
        print("❌ No data found to translate. Check 'data' folder.")
        return

    # 결과물 저장을 위한 디렉토리 생성
    os.makedirs(os.path.dirname(FINAL_FILE), exist_ok=True)

    # 캐시 로드
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    
    # 미번역 항목 선별
    to_translate = []
    for item in items:
        key = f"{item['code']}_{item['original']}"
        if key not in cache:
            to_translate.append(item)
    
    print(f"Remaining items to translate: {len(to_translate)}")
    if not to_translate:
        print("All items translated!")
        # 그래도 FINAL 파일은 생성해야 함 (캐시 내용으로)
        print(f"Saving final results to {FINAL_FILE}...")
        with open(FINAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        return

    system_prompt = get_system_prompt()
    
    async with aiohttp.ClientSession() as session:
        # BATCH_SIZE 단위로 처리하되, tqdm은 아이템 단위로 표시
        pbar = tqdm(total=len(to_translate), desc="Translating Items")
        for i in range(0, len(to_translate), BATCH_SIZE):
            batch = to_translate[i:i+BATCH_SIZE]
            tasks = [translate_item(session, item['code'], item['original'], system_prompt) for item in batch]
            results = await asyncio.gather(*tasks)
            
            # 결과 저장 (캐시 업데이트)
            changed = False
            for item, res in zip(batch, results):
                if res:
                    key = f"{item['code']}_{item['original']}"
                    cache[key] = {
                        "code": item['code'],
                        "original": item['original'],
                        "category": item['category'],
                        "translated": res.get("translated", ""),
                        "tts_phrase": res.get("tts_phrase", ""),
                        "summary": res.get("summary", "")
                    }
                    changed = True
            
            # 주기적으로 캐시 파일 저장
            if changed:
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
            
            pbar.update(len(batch))
        pbar.close()

    # 최종 결과 파일 생성 (통합본)
    print(f"Saving combined results to {FINAL_FILE}...")
    with open(FINAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    # ---------------------------------------------------------
    # 4. 소스별 개별 파일 분리 저장 (사용자 요청 사항)
    # ---------------------------------------------------------
    print("\n--- Exporting individual files ---")
    for source_key, source_path in DATA_SOURCES.items():
        if not os.path.exists(source_path): continue
        
        # 이름 생성: github_dtc_bulk.json -> github_dtc_bulk_translated.json
        base_name = os.path.splitext(source_path)[0]
        output_filename = f"{base_name}_translated.json"
        
        print(f"Exporting {source_key} -> {output_filename}...")
        
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
            
            # 리스트나 딕셔너리 처리 (DB 파일 등 구조가 다를 수 있음)
            # 여기서는 JSON 파일들만 처리한다고 가정 (DB는 위에서 읽기만 했으므로 패스하거나 별도 처리 필요하지만, 
            # 사용자 요청 파일 4개는 모두 JSON이므로 통용됨)
            
            export_list = []
            
            # DB의 경우 original_data가 list가 아닐 수 있음 (위 load_all_data는 DB 직접 접속함)
            # 따라서 JSON 파일인 경우만 처리
            if source_key == "db": 
                continue 

            items = original_data if isinstance(original_data, list) else [original_data]
            
            for item in items:
                code = item.get('code', 'UNKNOWN')
                orig = item.get('original_context', '')
                
                # 원본 복사
                new_item = item.copy()
                
                # 캐시에서 번역 찾기
                key = f"{code}_{orig}"
                if key in cache:
                    cached_item = cache[key]
                    if cached_item.get('translated'):
                        new_item['korean_translation'] = cached_item['translated']
                        new_item['tts_phrase'] = cached_item['tts_phrase']
                        new_item['summary_ko'] = cached_item['summary']
                
                export_list.append(new_item)
                    
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(export_list, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error exporting {source_key}: {e}")

    print("\nTranslation & Export completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
