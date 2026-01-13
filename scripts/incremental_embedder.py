import os
import json
import sqlite3
import hashlib
import time
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 ---
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432),
    "database": os.getenv("DB_NAME", "car_sentry"),
    "user": os.getenv("DB_USER", "Ai-5-main-project"),
    "password": os.getenv("DB_PASSWORD", "Ai5MainProj")
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
                id SERIAL PRIMARY KEY,
                content TEXT,
                metadata JSONB,
                category TEXT,
                embedding vector(384),
                content_hash TEXT UNIQUE
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

def main():
    print("="*60)
    print("RAG Incremental Sync Engine")
    print("="*60)
    
    sqlite_conn = init_tracker()
    pg_conn = init_vector_db()
    if not pg_conn: return

    print(f"Loading model: {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
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
