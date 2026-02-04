import os
import json
import hashlib
import time
import requests
import shutil
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 ---
SOURCE_DIR = "data/manuals/parsed"
DEST_DIR = "data/manuals/embedded"
OUTPUT_SQL_PATH = "db/seed_knowledge_vectors.sql"
LOG_FILE = "logs/embed_pipeline.log"

MODEL_NAME = "nomic-embed-text"  # 768차원, 고속 모델
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

import re

def clean_text(text):
    if not text: return ""
    # 1. SQL 이스케이프 및 NULL 문자 제거
    text = text.replace('\x00', '').replace("'", "''")
    # 2. 제어 문자 및 비인쇄 문자 제거 (Regex)
    text = re.sub(r'[\x00-\x1f\x7f-\xad]', ' ', text)
    # 3. 연속된 공백 및 줄바꿈을 단일 공백으로 치환
    text = " ".join(text.split())
    return text.strip()

def get_ollama_embedding(text):
    """Ollama API를 통해 텍스트 임베딩 생성"""
    try:
        response = requests.post(OLLAMA_API_URL, json={
            "model": MODEL_NAME,
            "prompt": text
        }, timeout=90) # 타임아웃 90초로 상향
        
        if response.status_code == 200:
            return response.json().get("embedding")
        else:
            log(f"  [ERROR] Ollama API Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        log(f"  [ERROR] Ollama Timeout: API request timed out (60s)")
        return None
    except requests.exceptions.ConnectionError:
        log(f"  [ERROR] Ollama Connection Error: Failed to connect to Ollama server")
        return None
    except Exception as e:
        log(f"  [ERROR] Unexpected Embedding Error: {e}")
        return None

def format_sql(content, metadata, embedding, content_hash):
    emb_str = str(embedding)
    meta_str = json.dumps(metadata).replace("'", "''")
    return f"INSERT INTO knowledge_vectors (content, metadata, embedding, content_hash) VALUES ('{content}', '{meta_str}', '{emb_str}', '{content_hash}') ON CONFLICT (content_hash) DO NOTHING;\n"

import urllib.parse

def extract_metadata_from_filename(filename):
    """
    파일명에서 제조사, 연식, 모델명을 추출합니다.
    예: Audi_2010_A3_%288PA%29_L4-2.0L_Turbo_%28CCTA%29_full.json
    """
    # URL 인코딩 제거 (예: %20 -> space)
    decoded_name = urllib.parse.unquote(filename)
    
    # 확장자 제거 및 _full 접미사 제거
    base_name = decoded_name.replace(".json", "").replace("_full", "")
    
    # 패턴: Manufacturer_Year_Model_Rest
    # 연식을 기준으로 분리 시도 (4자리 숫자)
    match = re.search(r'^([^_]+)_(\d{4})_(.+)$', base_name)
    
    if match:
        manufacturer = match.group(1)
        year = match.group(2)
        model_part = match.group(3)
        
        # 모델명은 보통 연식 이후 첫 번째 또는 두 번째 섹션까지
        # 너무 길어지지 않게 적절히 자름 (보통 _L4, _V6 등 엔진 정보 전까지)
        model_name = re.split(r'_(?:[LV]\d|Hybrid|Electric|AWD|FWD|Quattro)', model_part)[0]
        model_name = model_name.replace("_", " ").strip()
        
        return {
            "manufacturer": manufacturer,
            "year": year,
            "model_name": model_name
        }
    
    return {}

def process_file(filepath):
    filename = os.path.basename(filepath)
    log(f"Starting embedding for {filename}...")
    
    # 파일명에서 메타데이터 미리 추출
    file_metadata = extract_metadata_from_filename(filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            data_list = json.load(f)
            
        if not isinstance(data_list, list):
            log(f"  [SKIP] {filename} is not a valid list format.")
            return False

        success_count = 0
        error_count = 0
        
        with open(OUTPUT_SQL_PATH, 'a', encoding='utf-8') as sql_f:
            for item_idx, item in enumerate(data_list):
                raw_content = item.get("content", item.get("original_context", ""))
                if not raw_content: continue
                
                # 최적화된 청킹 (1000자)
                chunk_size = 1000
                content_chunks = [raw_content[i:i+chunk_size] for i in range(0, len(raw_content), chunk_size)]
                
                for idx, chunk in enumerate(content_chunks):
                    chunk = clean_text(chunk)
                    if not chunk: continue
                    
                    embedding = get_ollama_embedding(chunk)
                    
                    if not embedding:
                        error_count += 1
                        continue
                    
                    metadata = {k: v for k, v in item.items() if k not in ["content", "original_context"]}
                    
                    # 파일명에서 추출한 메타데이터 병합
                    metadata.update(file_metadata)
                    
                    metadata["source_file"] = filename
                    metadata["chunk_index"] = idx
                    metadata["item_index"] = item_idx
                    
                    content_hash = get_hash(f"{chunk}_{item_idx}_{idx}_{filename}")
                    
                    sql_line = format_sql(chunk, metadata, embedding, content_hash)
                    sql_f.write(sql_line)
                    success_count += 1
                
                if item_idx % 50 == 0:
                    log(f"  Progress: {item_idx}/{len(data_list)} items processed (Current Success: {success_count}, Error: {error_count})")

        log(f"  [FINISH] {filename}: Success {success_count} segments, Failed {error_count}")
        return True 
    except Exception as e:
        log(f"  [FATAL ERROR] Failed to process {filename}: {e}")
        return False

def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_SQL_PATH), exist_ok=True)
    
    if not os.path.exists(OUTPUT_SQL_PATH):
        with open(OUTPUT_SQL_PATH, 'w', encoding='utf-8') as f:
            f.write("-- Vector Knowledge Seed Data (Manuals - 768 Dim)\n\n")

    log("="*60)
    log(f"Manual Embedding Pipeline Started (Model: {MODEL_NAME})")
    log("="*60)

    while True:
        # data/manuals/parsed에서 .json 파일 목록 가져오기
        all_files = os.listdir(SOURCE_DIR)
        json_files = [f for f in all_files if f.endswith('.json')]
        
        if not json_files:
            log("No files to process. Waiting...")
            time.sleep(60)
            continue
            
        json_files.sort()
        
        for file in json_files:
            src_path = os.path.join(SOURCE_DIR, file)
            processing_path = src_path + ".processing"
            
            if not os.path.exists(src_path):
                continue
                
            try:
                # Atomic Lock 시도
                os.rename(src_path, processing_path)
                log(f"[LOCK] Acquired: {file}")
            except Exception:
                continue
                
            # 처리 수행
            if process_file(processing_path):
                dest_path = os.path.join(DEST_DIR, file)
                try:
                    shutil.move(processing_path, dest_path)
                    log(f"[FINISH] {file} (Done & Moved)")
                except Exception as e:
                    log(f"[ERROR] Move failed for {file}: {e}")
            else:
                # 실패 시 락 해제
                os.rename(processing_path, src_path)
                log(f"[RETRY] Restored {file}")
                time.sleep(5)
                
        time.sleep(5)

if __name__ == "__main__":
    main()
