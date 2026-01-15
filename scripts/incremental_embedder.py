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

# 로컬 임베딩 모델 (적당한 성능/속도 균형)
MODEL_NAME = "all-MiniLM-L6-v2"  # 1536 대신 384 차원 사용 (속도 향상)
BATCH_SIZE = 32

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
        
        # pgvector 확장 활성화
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 테이블 생성
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_vectors (
                knowledge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
                category VARCHAR(20),
                content TEXT,
                metadata JSONB,
                embedding vector(1024), -- 1024차원 (mxbai-embed-large)
                content_hash VARCHAR(64) UNIQUE
            );
        """)
        conn.commit()
        print("PGVector Table initialized.")
        return conn
    except Exception as e:
        print(f"Postgres connection failed: {e}")
        return None

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def clean_text(text):
    """Postgres가 싫어하는 NUL 문자 제거"""
    if not text: return ""
    return text.replace('\x00', '')

def process_and_embed(pg_conn, sqlite_conn, model, data_list):
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    new_items = []
    
    # 1. 중복 체크 (SQLite)
    for item in data_list:
        content = item.get("content", item.get("original_context", ""))
        content = clean_text(content) # 정제
        content_hash = get_hash(content)
        
        sqlite_cursor.execute("SELECT 1 FROM sync_history WHERE content_hash = ?", (content_hash,))
        if not sqlite_cursor.fetchone():
            item["content_hash"] = content_hash
            item["clean_content"] = content # 정제된 텍스트 보관
            new_items.append(item)
            
    if not new_items:
        return 0
    
    print(f"  Found {len(new_items)} new items to embed...")
    
    # 2. 배치 임베딩
    texts = [it["clean_content"] for it in new_items]
    embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=True)
    
    # 3. DB 적재 (Postgres)
    results_to_insert = []
    sync_logs = []
    
    for it, emb in zip(new_items, embeddings):
        content = it["clean_content"]
        category = it.get("category", "MANUAL")
        metadata = {k: v for k, v in it.items() if k not in ["content", "original_context", "content_hash", "category", "clean_content"]}
        
        results_to_insert.append((
            content,
            json.dumps(metadata),
            category,
            emb.tolist(),
            it["content_hash"]
        ))
        
        sync_logs.append((it["content_hash"], metadata.get("source", "DTC"), category))

    # PostgreSQL Bulk Insert
    execute_values(pg_cursor, """
        INSERT INTO knowledge_vectors (content, metadata, category, embedding, content_hash)
        VALUES %s
        ON CONFLICT (content_hash) DO NOTHING
    """, results_to_insert)
    
    # SQLite Bulk Log
    sqlite_cursor.executemany("""
        INSERT OR IGNORE INTO sync_history (content_hash, source, category)
        VALUES (?, ?, ?)
    """, sync_logs)
    
    pg_conn.commit()
    sqlite_conn.commit()
    
    return len(new_items)

import requests

# ... (기존 임포트 유지)

# 로컬 임베딩 모델 (Ollama)
MODEL_NAME = "mxbai-embed-large"  # 1024차원
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
BATCH_SIZE = 10 # Ollama는 배치 사이즈를 조금 작게 잡는 게 안정적

# ... (init_tracker, init_vector_db 유지) ...
# init_vector_db 내부의 vector(384) -> vector(1024) 변경도 필요하지만, 
# 이미 DB에서 테이블을 드랍하고 다시 만들었으므로 스크립트의 테이블 생성 코드는 
# 'IF NOT EXISTS' 때문에 무시되거나, 혹은 스크립트 내 정의도 1024로 맞춰주는 게 좋음.

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

def process_and_embed(pg_conn, sqlite_conn, model_unused, data_list):
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
    
    # 2. 임베딩 및 DB 적재 (Ollama는 배치 API가 공식적으로는 없거나 단일 처리가 기본이므로 루프 처리)
    # 속도를 위해 ThreadPoolExecutor 등을 쓸 수도 있지만, 일단 안정성을 위해 순차 처리
    
    results_to_insert = []
    sync_logs = []
    
    for i, it in enumerate(new_items):
        if i % 10 == 0: print(f"    Embedding {i}/{len(new_items)}...", end='\r')
        
        emb = get_ollama_embedding(it["clean_content"])
        if not emb: continue # 실패 시 스킵
        
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

    # PostgreSQL Bulk Insert
    if results_to_insert:
        execute_values(pg_cursor, """
            INSERT INTO knowledge_vectors (content, metadata, category, embedding, content_hash)
            VALUES %s
            ON CONFLICT (content_hash) DO NOTHING
        """, results_to_insert)
        
        # SQLite Bulk Log
        sqlite_cursor.executemany("""
            INSERT OR IGNORE INTO sync_history (content_hash, source, category)
            VALUES (?, ?, ?)
        """, sync_logs)
        
        pg_conn.commit()
        sqlite_conn.commit()
    
    return len(results_to_insert)
def main():
    print("="*60)
    print("RAG Incremental Sync Engine (Ollama - mxbai-embed-large)")
    print("="*60)
    
    sqlite_conn = init_tracker()
    pg_conn = init_vector_db()
    if not pg_conn: return

    # SentenceTransformer 모델 로드 부분 삭제됨 (Ollama API 사용)
    model = None 
    
    # --- 1. DTC 데이터 처리 ---
    if os.path.exists(DTC_JSON_PATH):
        print(f"Processing DTC: {DTC_JSON_PATH}")
        with open(DTC_JSON_PATH, 'r', encoding='utf-8') as f:
            dtc_data = json.load(f)
            count = process_and_embed(pg_conn, sqlite_conn, model, dtc_data)
            print(f"  -> Added {count} DTC vectors")

    # --- 2. 매뉴얼 데이터 처리 ---
    if os.path.exists(MANUAL_PARSED_DIR):
        files = [f for f in os.listdir(MANUAL_PARSED_DIR) if f.endswith('.json')]
        for filename in files:
            filepath = os.path.join(MANUAL_PARSED_DIR, filename)
            print(f"Processing Manual: {filename}")
            with open(filepath, 'r', encoding='utf-8') as f:
                manual_data = json.load(f)
                count = process_and_embed(pg_conn, sqlite_conn, model, manual_data)
                print(f"  -> Added {count} vectors")

    print("\n" + "="*60)
    print("Sync Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
