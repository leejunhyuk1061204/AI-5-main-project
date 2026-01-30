import os
import json
import hashlib
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 ---
DTC_JSON_PATH = "data/dtc/github_dtc_bulk.json"
OUTPUT_SQL_PATH = "db/seed_knowledge_vectors.sql"

MODEL_NAME = "mxbai-embed-large"  # 1024차원
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def clean_text(text):
    if not text: return ""
    return text.replace('\x00', '').replace("'", "''") # SQL Escape

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

def format_sql(content, metadata, category, embedding, content_hash):
    # PostgreSQL pgvector format: '[0.1, 0.2, ...]'
    emb_str = str(embedding)
    meta_str = json.dumps(metadata).replace("'", "''")
    return f"INSERT INTO knowledge_vectors (category, content, metadata, embedding, content_hash) VALUES ('{category}', '{content}', '{meta_str}', '{emb_str}', '{content_hash}') ON CONFLICT (content_hash) DO NOTHING;\n"

def main():
    print("="*60)
    print(f"Generating Vector Seed SQL Directly (Model: {MODEL_NAME})")
    print("="*60)

    if not os.path.exists("db"):
        os.makedirs("db")

    if not os.path.exists(DTC_JSON_PATH):
        print(f"Error: Source file {DTC_JSON_PATH} not found.")
        return

    print(f"Reading {DTC_JSON_PATH}...")
    with open(DTC_JSON_PATH, 'r', encoding='utf-8') as f:
        dtc_data = json.load(f)

    total = len(dtc_data)
    print(f"Total items to process: {total}")

    # 새 파일 시작 (헤더 작성)
    with open(OUTPUT_SQL_PATH, 'w', encoding='utf-8') as f:
        f.write("-- Vector Knowledge Seed Data\n")
        f.write("-- Generated via scripts/generate_vector_seed.py\n\n")

    for i, item in enumerate(dtc_data):
        content = item.get("original_context", item.get("content", ""))
        content = clean_text(content)
        if not content:
            continue

        if i % 10 == 0:
            print(f"Progress: {i}/{total} ({(i/total)*100:.1f}%)", end='\r')

        embedding = get_ollama_embedding(content)
        if not embedding:
            continue

        category = "DTC"
        metadata = {k: v for k, v in item.items() if k not in ["original_context", "content"]}
        content_hash = get_hash(content)

        sql_line = format_sql(content, metadata, category, embedding, content_hash)

        # 즉시 파일에 쓰기 (Append mode)
        with open(OUTPUT_SQL_PATH, 'a', encoding='utf-8') as f:
            f.write(sql_line)

    print(f"\nSuccessfully generated {OUTPUT_SQL_PATH}")
    print("="*60)

if __name__ == "__main__":
    main()
