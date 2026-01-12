import os
import json
import zipfile
from bs4 import BeautifulSoup
import time

# --- 설정 ---
ZIP_DIR = "data/manuals/zips"
OUTPUT_PATH = "data/manuals/parsed_manuals.json"
MAX_CONTENT_LENGTH = 5000  # 청킹용 최대 길이
# ---

def extract_text_from_html(html_content):
    """HTML에서 텍스트 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 스크립트, 스타일 제거
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    
    text = soup.get_text(separator='\n', strip=True)
    return text

def process_zip_file(zip_path):
    """ZIP 파일에서 HTML 추출 및 파싱"""
    results = []
    filename = os.path.basename(zip_path)
    
    parts = filename.replace('.zip', '').split('_')
    brand = parts[0]
    year = parts[1]
    model = '_'.join(parts[2:])
    
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
                        
                        if len(text) > 300:  # 최소 길이 상향 (노이즈 방지)
                            results.append({
                                "brand": brand,
                                "year": year,
                                "model": model.replace('_', ' '),
                                "source": html_file,
                                "category": "MANUAL",
                                "content": text[:MAX_CONTENT_LENGTH], # 전체 파싱이므로 청킹은 나중에 DB 적재 시 수행
                                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                except:
                    pass
                
                if (i + 1) % 500 == 0:
                    print(f"    Processed {i+1}/{total} files...")
                    
    except Exception as e:
        print(f"  Error: {e}")
    
    return results

def main():
    print("="*60)
    print("FULL ZIP to JSON Parser for RAG")
    print("="*60)
    
    zip_files = [f for f in os.listdir(ZIP_DIR) if f.endswith('.zip')]
    
    for zip_file in zip_files:
        zip_path = os.path.join(ZIP_DIR, zip_file)
        # 차량별 개별 JSON 저장 (대용량 관리 용이)
        output_name = zip_file.replace('.zip', '_full.json')
        output_path = os.path.join("data/manuals/parsed", output_name)
        
        if os.path.exists(output_path):
            print(f"Skipping {zip_file}, already parsed.")
            continue
            
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        results = process_zip_file(zip_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        file_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"  -> Saved {len(results)} pages ({file_size:.1f} MB)")
        
        # 파싱 성공 후 원본 ZIP 삭제 (저장 공간 최적화)
        try:
            os.remove(zip_path)
            print(f"  -> Original ZIP deleted to save space.\n")
        except Exception as e:
            print(f"  -> Failed to delete ZIP: {e}\n")
    
    print("="*60)
    print(f"Complete! All files saved in data/manuals/parsed/")
    print("="*60)

if __name__ == "__main__":
    main()
