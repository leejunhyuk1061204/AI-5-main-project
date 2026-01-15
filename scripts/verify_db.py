
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='car_sentry',
        user='Ai-5-main-project',
        password='Ai5MainProjectPassword'
    )
    cur = conn.cursor()
    
    cur.execute('SELECT count(*) FROM knowledge_vectors')
    count = cur.fetchone()[0]
    print(f'Row Count: {count}')
    
    cur.execute('SELECT vector_dims(embedding) FROM knowledge_vectors LIMIT 1')
    res = cur.fetchone()
    if res:
        print(f'Dimensions: {res[0]}')
    else:
        print('Dimensions: No data (Table empty)')
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
