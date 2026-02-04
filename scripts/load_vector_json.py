import os
import json
import psycopg2
from psycopg2.extras import execute_values
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

SEED_FILE = "db/seed_knowledge_vectors.json"

def main():
    print("="*60)
    print(f"Loading Vector JSON Seed into Database")
    print("="*60)

    if not os.path.exists(SEED_FILE):
        print(f"Error: Seed file {SEED_FILE} not found. Run generate_vector_json.py first.")
        return

    try:
        print(f"Connecting to database {DB_CONFIG['database']}...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print(f"Reading {SEED_FILE}...")
        with open(SEED_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"Preparing {len(data)} items for bulk insert...")
        
        insert_data = []
        for item in data:
            insert_data.append((
                item['category'],
                item['content'],
                json.dumps(item['metadata']),
                item['embedding'],
                item['content_hash']
            ))

        print("Executing bulk insert (ON CONFLICT DO NOTHING)...")
        execute_values(cursor, """
            INSERT INTO knowledge_vectors (category, content, metadata, embedding, content_hash)
            VALUES %s
            ON CONFLICT (content_hash) DO NOTHING
        """, insert_data)

        conn.commit()
        print(f"Successfully loaded data into knowledge_vectors.")
        
        # Verify
        cursor.execute("SELECT count(*) FROM knowledge_vectors;")
        count = cursor.fetchone()[0]
        print(f"Current total rows in knowledge_vectors: {count}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

    print("="*60)

if __name__ == "__main__":
    main()
