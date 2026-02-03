import os
import json
import sqlite3
import hashlib
import time
import psycopg2
from psycopg2.extras import execute_values
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 ---
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432),
    "database": os.getenv("DB_NAME", "car_sentry"),
    "user": os.getenv("DB_USER", "Ai-5-main-project"),
    "password": os.getenv("DB_PASSWORD", "Ai5MainProjectPassword")
}

TRACKER_DB_PATH = "data/sync_tracker.db"
MANUAL_PARSED_DIR = "data/manuals/parsed"
DTC_JSON_PATH = "data/dtc/github_dtc_bulk.json"

# 로컬 임베딩 모델 (Ollama)
MODEL_NAME = "mxbai-embed-large"  # 1024차원
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
BATCH_SIZE = 10 

# --- 초기화 ---
def init_tracker():
    conn = sqlite3.connect(TRACKER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_history (
            content_hash TEXT PRIMARY KEY,
            source TEXT,
            category TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def init_vector_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # pgvector 필요 (이미 설치되어 있다고 가정)
        # cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;") # 권한 문제 가능성 있으므로 필요시 주석 해제

        # 테이블 생성 (벡터 차원 1024 확인)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_vectors (
                knowledge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
                category VARCHAR(20),
                content TEXT,
                metadata JSONB,
                embedding vector(1024), 
                content_hash VARCHAR(64) UNIQUE
            );
        """)
        conn.commit()
        print("PGVector Table initialized/verified.")
        return conn
    except Exception as e:
        print(f"Postgres connection failed: {e}")
        return None

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def clean_text(text):
    if not text: return ""
    return text.replace('\x00', '')

def get_ollama_embedding(text):
    """Ollama API를 통해 텍스트 임베딩 생성"""
    try:
        response = requests.post(OLLAMA_API_URL, json={
            "model": MODEL_NAME,
            "prompt": text
        })
        if response.status_code == 200:
            return response.json().get("embedding")
        else:
            print(f"Ollama API Error: {response.text}")
            return None
    except Exception as e:
        print(f"Ollama Connection Error: {e}")
        return None

def process_and_embed(pg_conn, sqlite_conn, data_list):
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    new_items = []
    
    # 1. 중복 체크 (SQLite)
    for item in data_list:
        content = item.get("content", item.get("original_context", ""))
        content = clean_text(content)
        content_hash = get_hash(content)
        
        sqlite_cursor.execute("SELECT 1 FROM sync_history WHERE content_hash = ?", (content_hash,))
        if not sqlite_cursor.fetchone():
            item["content_hash"] = content_hash
            item["clean_content"] = content
            new_items.append(item)
            
    if not new_items:
        return 0
    
    print(f"  Found {len(new_items)} new items to embed...")
    
    results_to_insert = []
    sync_logs = []
    
    for i, it in enumerate(new_items):
        if i % 10 == 0: print(f"    Embedding {i}/{len(new_items)}...", end='\r')
        
        emb = get_ollama_embedding(it["clean_content"])
        if not emb: continue 
        
        content = it["clean_content"]
        category = it.get("category", "MANUAL")
        metadata = {k: v for k, v in it.items() if k not in ["content", "original_context", "content_hash", "category", "clean_content"]}
        
        results_to_insert.append((
            content,
            json.dumps(metadata),
            category,
            emb,
            it["content_hash"]
        ))
        
        sync_logs.append((it["content_hash"], metadata.get("source", "DTC"), category))

    print(f"    Embedding done. Inserting into DB...")

    if results_to_insert:
        execute_values(pg_cursor, """
            INSERT INTO knowledge_vectors (content, metadata, category, embedding, content_hash)
            VALUES %s
            ON CONFLICT (content_hash) DO NOTHING
        """, results_to_insert)
        
        sqlite_cursor.executemany("""
            INSERT OR IGNORE INTO sync_history (content_hash, source, category)
            VALUES (?, ?, ?)
        """, sync_logs)
        
        pg_conn.commit()
        sqlite_conn.commit()
    
    return len(results_to_insert)

def main():
    print("="*60)
    print(f"RAG Incremental Sync Engine (Ollama - {MODEL_NAME})")
    print("="*60)
    
    sqlite_conn = init_tracker()
    pg_conn = init_vector_db()
    if not pg_conn: return

    # --- 1. DTC 데이터 처리 ---
    if os.path.exists(DTC_JSON_PATH):
        print(f"Processing DTC: {DTC_JSON_PATH}")
        with open(DTC_JSON_PATH, 'r', encoding='utf-8') as f:
            dtc_data = json.load(f)
            count = process_and_embed(pg_conn, sqlite_conn, dtc_data)
            print(f"  -> Added {count} DTC vectors")

    # --- 2. 매뉴얼 데이터 처리 ---
    if os.path.exists(MANUAL_PARSED_DIR):
        files = [f for f in os.listdir(MANUAL_PARSED_DIR) if f.endswith('.json')]
        for filename in files:
            filepath = os.path.join(MANUAL_PARSED_DIR, filename)
            print(f"Processing Manual: {filename}")
            with open(filepath, 'r', encoding='utf-8') as f:
                manual_data = json.load(f)
                count = process_and_embed(pg_conn, sqlite_conn, manual_data)
                print(f"  -> Added {count} vectors")

    print("\n" + "="*60)
    print("Sync Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
