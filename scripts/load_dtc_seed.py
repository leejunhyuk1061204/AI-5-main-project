import psycopg2
import os
import sys

# DB Config (matching application.yml defaults)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "car_sentry")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres") # <--- 여기를 사용자의 실제 비밀번호로 변경해주세요

SEED_FILE = "db/seed_dtc.sql"

def main():
    print(f"Connecting to {DB_NAME} at {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Read SQL file
        print(f"Reading {SEED_FILE}...")
        with open(SEED_FILE, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        lines = sql_content.splitlines()
        insert_commands = [line for line in lines if line.strip().startswith("INSERT")]
        print(f"Found {len(insert_commands)} INSERT statements.")
        
        # 2. Execute
        print("Executing SQL (this might take a moment)...")
        # To avoid memory issues with huge block, execute line by line or in chunks if needed.
        # But 38k lines is manageable for pg. Let's try executing the whole file or large chunks.
        # Actually, executing line by line with progress bar is better for UR.
        
        success_count = 0
        error_count = 0
        
        for i, cmd in enumerate(insert_commands):
            try:
                cursor.execute(cmd)
                success_count += 1
            except Exception as e:
                print(f"Error on line {i+1}: {e}")
                error_count += 1
                
            if (i+1) % 1000 == 0:
                print(f"  Processed {i+1}/{len(insert_commands)}...")
                
        print(f"\nLoad Complete.")
        print(f"  Success: {success_count}")
        print(f"  Errors : {error_count}")
        
        # 3. Verification
        print("\nVerifying 'knowledge_vectors' table count...")
        cursor.execute("SELECT count(*) FROM knowledge_vectors WHERE category='DTC_GUIDE'")
        cnt = cursor.fetchone()[0]
        print(f"  Total DTC_GUIDE records in DB: {cnt}")
        
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    main()
