import os
import json
import time
import zipfile
import requests
from bs4 import BeautifulSoup

# --- 설정 ---
ZIP_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
MAX_CONTENT_LENGTH = 5000
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3" # 사용자 환경에 맞춰 변경 가능 (예: llama3, mistral 등)

def translate_text_ollama(text):
    """Ollama를 사용하여 텍스트 번역 (간결한 요약 번역)"""
    if not text or len(text.strip()) < 10:
        return ""
    
    prompt = f"Translate the following automotive repair manual text into natural Korean. Output only the translation:\n\n{text[:1000]}"
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get('response', '').strip()
    except Exception as e:
        print(f"      [Translation Error] {e}")
    return ""

def extract_text_from_html(html_content):
    """HTML에서 텍스트 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    return soup.get_text(separator='\n', strip=True)

def process_zip_file(zip_path):
    """ZIP 파일에서 HTML 추출, 파싱 및 번역"""
    results = []
    filename = os.path.basename(zip_path)
    parts = filename.replace('.zip', '').split('_')
    brand, year = parts[0], parts[1]
    model = ' '.join(parts[2:]).replace('_', ' ')
    
    print(f"Processing: {filename}")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            html_files = [f for f in zf.namelist() if f.endswith(('.html', '.htm'))]
            total = len(html_files)
            print(f"  Found {total} HTML files")
            
            for i, html_file in enumerate(html_files):
                try:
                    with zf.open(html_file) as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        text = extract_text_from_html(content)
                        
                        if len(text) > 300:
                            # 번역 수행
                            translated_text = translate_text_ollama(text)
                            
                            results.append({
                                "brand": brand,
                                "year": year,
                                "model": model,
                                "source": html_file,
                                "category": "MANUAL",
                                "content": text[:MAX_CONTENT_LENGTH],
                                "content_ko": translated_text,
                                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                except:
                    pass
                
                if (i + 1) % 100 == 0:
                    print(f"    Processed {i+1}/{total} files (with translation)...")
                    
    except Exception as e:
        print(f"  Error: {e}")
    
    return results

def main():
    os.makedirs(PARSED_DIR, exist_ok=True)
    zip_files = [f for f in os.listdir(ZIP_DIR) if f.endswith('.zip')]
    
    for zip_file in zip_files:
        zip_path = os.path.join(ZIP_DIR, zip_file)
        output_name = zip_file.replace('.zip', '_full.json')
        output_path = os.path.join(PARSED_DIR, output_name)
        
        if os.path.exists(output_path):
            print(f"Skipping {zip_file}, already parsed.")
            continue
            
        results = process_zip_file(zip_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print(f"  -> Saved {len(results)} pages. Deleting ZIP...")
        try:
            os.remove(zip_path)
        except:
            pass

if __name__ == "__main__":
    main()
