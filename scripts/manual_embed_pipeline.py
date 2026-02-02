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

MODEL_NAME = "bge-m3"  # 1024차원, 8192 컨텍스트 지원
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
            "prompt": text,
            "options": {
                "num_ctx": 8192  # BGE-M3의 최대 컨텍스트 활용
            }
        }, timeout=60) # 타임아웃 60초로 상향
        
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

def format_sql(content, metadata, category, embedding, content_hash):
    emb_str = str(embedding)
    meta_str = json.dumps(metadata).replace("'", "''")
    return f"INSERT INTO knowledge_vectors (category, content, metadata, embedding, content_hash) VALUES ('{category}', '{content}', '{meta_str}', '{emb_str}', '{content_hash}') ON CONFLICT (content_hash) DO NOTHING;\n"

def process_file(filepath):
    filename = os.path.basename(filepath)
    log(f"Starting embedding for {filename}...")
    
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
                
                # 매우 보수적인 청킹 (300자)
                chunk_size = 300
                content_chunks = [raw_content[i:i+chunk_size] for i in range(0, len(raw_content), chunk_size)]
                
                for idx, chunk in enumerate(content_chunks):
                    chunk = clean_text(chunk)
                    if not chunk: continue
                    
                    embedding = get_ollama_embedding(chunk)
                    
                    if not embedding:
                        # 300자에서도 실패한다면 기록하고 스킵
                        error_count += 1
                        continue
                    
                    category = "MANUAL"
                    metadata = {k: v for k, v in item.items() if k not in ["content", "original_context"]}
                    metadata["source_file"] = filename
                    metadata["chunk_index"] = idx
                    metadata["item_index"] = item_idx
                    
                    content_hash = get_hash(f"{chunk}_{item_idx}_{idx}_{filename}")
                    
                    sql_line = format_sql(chunk, metadata, category, embedding, content_hash)
                    sql_f.write(sql_line)
                    success_count += 1
                
                if item_idx % 50 == 0:
                    log(f"  Progress: {item_idx}/{len(data_list)} items processed (Current Success: {success_count}, Error: {error_count})")

        log(f"  [FINISH] {filename}: Success {success_count} segments, Failed {error_count}")
        return True # 일부 실패하더라도 파일은 이동 (무한루프 방지)
    except Exception as e:
        log(f"  [FATAL ERROR] Failed to process {filename}: {e}")
        return False

def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_SQL_PATH), exist_ok=True)
    
    if not os.path.exists(OUTPUT_SQL_PATH):
        with open(OUTPUT_SQL_PATH, 'w', encoding='utf-8') as f:
            f.write("-- Vector Knowledge Seed Data (Manuals - 1024 Dim)\n\n")

    log("="*60)
    log(f"Manual Embedding Pipeline Started (Model: {MODEL_NAME})")
    log("="*60)

    while True:
        files = [f for f in os.listdir(SOURCE_DIR) if f.endswith('.json')]
        
        if not files:
            time.sleep(15)
            continue
            
        for filename in files:
            src_path = os.path.join(SOURCE_DIR, filename)
            dest_path = os.path.join(DEST_DIR, filename)
            
            if process_file(src_path):
                try:
                    shutil.move(src_path, dest_path)
                    log(f"  [MOVE] Moved {filename} to {DEST_DIR}")
                except Exception as e:
                    log(f"  [ERROR] Failed to move {filename}: {e}")
            else:
                log(f"  [RETRY] Fatal error for {filename}, will retry.")
                time.sleep(10)
                
        time.sleep(10)

if __name__ == "__main__":
    main()
