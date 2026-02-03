import os
import json
import hashlib
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# --- 설정 ---
DTC_JSON_PATH = "data/dtc/github_dtc_bulk.json"
OUTPUT_JSON_PATH = "db/seed_knowledge_vectors.json"

MODEL_NAME = "mxbai-embed-large"  # 1024차원
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"

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

def main():
    print("="*60)
    print(f"Creating Embedded JSON Seed (Model: {MODEL_NAME})")
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

    embedded_data = []

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

        # 결과물 구조화
        vector_item = {
            "category": "DTC",
            "content": content,
            "embedding": embedding,
            "content_hash": get_hash(content),
            "metadata": {k: v for k, v in item.items() if k not in ["original_context", "content"]}
        }
        embedded_data.append(vector_item)

        # 중간 저장 (사용자가 파일 생성을 확인할 수 있도록 100개마다 저장)
        if (i + 1) % 100 == 0:
            with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(embedded_data, f, ensure_ascii=False, indent=2)

    print(f"\nWriting to {OUTPUT_JSON_PATH}...")
    with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(embedded_data, f, ensure_ascii=False, indent=2)

    print("="*60)
    print(f"Successfully generated embedded JSON seed with {len(embedded_data)} items.")
    print("="*60)

if __name__ == "__main__":
    main()
