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
MODEL_NAME = "qwen2.5:32b"
BATCH_SIZE = 5  # 병렬 처리 개수 (GPU 메모리에 따라 조절 가능)

DATA_SOURCES = {
    "bulk": "data/dtc/github_dtc_bulk.json",
    "summary": "data/dtc/batch_dtc_summary.json",
    "db": "data/dtc/github_dtc_codes.db"
}

CACHE_FILE = "data/dtc/translated_cache.json"
FINAL_FILE = "data/dtc/translated_dtc_final.json"

# --- 시스템 프롬프트 구성 ---
def get_system_prompt():
    terms_str = "\n".join([f"- {en}: {ko}" for en, ko in AUTOMOTIVE_TERMS.items()])
    return f"""너는 숙련된 자동차 정비 전문가이자 TTS(Text-to-Speech) 전문 성우야.
제공된 [자동차 용어 사전]을 참고해서 다음 규칙을 반드시 지켜서 번역해줘:

1. 전문 용어는 사전에 정의된 표준 번역어를 최우선으로 사용하되, 문맥에 맞게 자연스럽게 연결해줘.
2. **TTS 최적화**: 운전자가 운전 중에 들어도 한 번에 이해할 수 있도록 부드러운 구어체(~입니다, ~가 발생했습니다 등) 문장으로 구성해줘.
3. **구조화된 출력**: 반드시 아래의 JSON 형식으로만 응답해줘. 다른 설명은 하지 마.

[자동차 용어 사전]
{terms_str}

[출력 JSON 형식 교본]
{{
    "translated": "한글 번역문",
    "tts_phrase": "운전자를 위한 자연스러운 안내 문구",
    "summary": "핵심 요약 (5자 이내)"
}}
"""

async def translate_item(session, code, original, system_prompt):
    """Ollama API를 통해 단일 항목 번역 요청"""
    prompt = f"DTC 코드: {code}\n영문 원문: {original}\n\n위 내용을 규칙에 맞춰 번역해줘."
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        async with session.post(OLLAMA_URL, json=payload, timeout=60) as response:
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
    
    # 1. Bulk JSON
    if os.path.exists(DATA_SOURCES["bulk"]):
        with open(DATA_SOURCES["bulk"], 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                code = item.get('code', 'UNKNOWN')
                orig = item.get('original_context', '')
                if orig:
                    key = f"{code}_{orig}"
                    all_dtcs[key] = {"code": code, "original": orig, "category": "DEFINITION"}

    # 2. Summary JSON
    if os.path.exists(DATA_SOURCES["summary"]):
        with open(DATA_SOURCES["summary"], 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                code = item.get('code', 'UNKNOWN')
                orig = item.get('original_context', '')
                if orig:
                    key = f"{code}_{orig}"
                    all_dtcs[key] = {"code": code, "original": orig, "category": "SUMMARY"}

    # 3. SQLite DB
    if os.path.exists(DATA_SOURCES["db"]):
        conn = sqlite3.connect(DATA_SOURCES["db"])
        cursor = conn.cursor()
        cursor.execute("SELECT code, description FROM dtc_definitions")
        for code, desc in cursor.fetchall():
            if desc:
                key = f"{code}_{desc}"
                all_dtcs[key] = {"code": code, "original": desc, "category": "DB_DEFINITION"}
        conn.close()

    return list(all_dtcs.values())

async def main():
    # 데이터 로드
    items = load_all_data()
    print(f"Total unique DTC items to translate: {len(items)}")

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

    # 최종 결과 파일 생성
    print(f"Saving final results to {FINAL_FILE}...")
    with open(FINAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print("Translation completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
