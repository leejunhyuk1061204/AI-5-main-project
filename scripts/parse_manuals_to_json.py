import os
import json
import time
import zipfile
from bs4 import BeautifulSoup

# --- 설정 ---
ZIP_DIR = "data/manuals/zips"
PARSED_DIR = "data/manuals/parsed"
MAX_CONTENT_LENGTH = 5000

def extract_text_from_html(html_content):
    """HTML에서 텍스트 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    return soup.get_text(separator='\n', strip=True)

def process_zip_file(zip_path):
    """ZIP 파일에서 HTML 추출 및 파싱 (번역 제외)"""
    results = []
    filename = os.path.basename(zip_path)
    # 파일명 형식: Brand_Year_Model...zip
    parts = filename.replace('.zip', '').split('_')
    if len(parts) < 3:
        print(f"  Invalid filename format: {filename}")
        return results
        
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
                            results.append({
                                "brand": brand,
                                "year": year,
                                "model": model,
                                "source": html_file,
                                "category": "MANUAL",
                                "content": text[:MAX_CONTENT_LENGTH],
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
    os.makedirs(PARSED_DIR, exist_ok=True)
    if not os.path.exists(ZIP_DIR):
        print(f"Directory not found: {ZIP_DIR}")
        return

    zip_files = [f for f in os.listdir(ZIP_DIR) if f.endswith('.zip')]
    print(f"Found {len(zip_files)} ZIP files to process.")
    
    for zip_file in zip_files:
        zip_path = os.path.join(ZIP_DIR, zip_file)
        # 이미 처리된 파일인지 확인 (확장자 제거 후 _full.json 붙임)
        output_name = zip_file.replace('.zip', '_full.json')
        output_path = os.path.join(PARSED_DIR, output_name)
        
        if os.path.exists(output_path):
            # print(f"Skipping {zip_file}, already parsed.")
            continue
            
        results = process_zip_file(zip_path)
        
        if results:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"  -> Saved {len(results)} pages. Deleting ZIP...")
            try:
                os.remove(zip_path)
            except Exception as e:
                print(f"  Failed to delete {zip_file}: {e}")
        else:
            print(f"  No valid content found in {zip_file}. Skipping deletion to be safe.")

if __name__ == "__main__":
    main()
