import argparse
import os
import json
import hashlib
import time
import urllib.parse
import requests
import zipfile
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path

# --- 설정 ---
SOURCE_DIR = r"G:\내 드라이브\정비지침서\원본_zip"
OUTPUT_SQL_PATH = "db/seed_manual_chunks.sql"
LOG_FILE = "logs/embed_manuals.log"

MODEL_NAME = "nomic-embed-text"
OLLAMA_API_URL = "http://localhost:11434/api/embed"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_RETRIES = 3
EMBED_RETRY_DELAY = 5
PROCESSED_LIST_FILE = "logs/embed_manuals_processed.txt"

def log(message):
    """로그 출력 및 파일 저장"""
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

def get_hash(text):
    """텍스트 해시 생성 (중복 방지)"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def clean_text(text):
    """SQL 안전 텍스트 정리"""
    if not text: return ""
    text = text.replace('\x00', '').replace("'", "''")
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xad]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# --- Smart Chunking Logic (기존과 동일) ---
class SmartTextSplitter:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # 우선순위: 문단 -> 줄 -> 문장 -> 공백 -> 글자
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text):
        final_chunks = []
        self._split_recursive(text, self.separators, final_chunks)
        return final_chunks

    def _split_recursive(self, text, separators, final_chunks):
        if len(text) <= self.chunk_size:
            final_chunks.append(text)
            return

        separator = ""
        next_separators = []
        
        for i, sep in enumerate(separators):
            if sep in text:
                separator = sep
                next_separators = separators[i+1:]
                break
        
        if not separator and not next_separators:
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                final_chunks.append(text[i:i+self.chunk_size])
            return

        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)

        good_splits = []
        for s in splits:
            if separator != "": s = s.strip()
            if not s: continue
            
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if next_separators:
                    sub_chunks = []
                    self._split_recursive(s, next_separators, sub_chunks)
                    good_splits.extend(sub_chunks)
                else:
                    good_splits.append(s)

        self._merge_splits(good_splits, separator, final_chunks)

    def _merge_splits(self, splits, separator, final_chunks):
        current_doc = []
        current_len = 0
        
        for s in splits:
            s_len = len(s)
            sep_len = len(separator) if current_len > 0 else 0
            
            if current_len + s_len + sep_len > self.chunk_size:
                if current_doc:
                    chunk_text = separator.join(current_doc)
                    final_chunks.append(chunk_text)
                    
                    overlap_doc = []
                    overlap_len = 0
                    for seg in reversed(current_doc):
                        seg_len = len(seg)
                        s_sep = len(separator) if overlap_len > 0 else 0
                        if overlap_len + seg_len + s_sep > self.chunk_overlap:
                            break
                        overlap_doc.insert(0, seg)
                        overlap_len += seg_len + s_sep
                    
                    current_doc = overlap_doc
                    current_len = overlap_len
            
            current_doc.append(s)
            current_len += s_len + (len(separator) if current_len > 0 else 0)
        
        if current_doc:
            final_chunks.append(separator.join(current_doc))

splitter = SmartTextSplitter(CHUNK_SIZE, CHUNK_OVERLAP)

def extract_metadata_from_zipname(zipname):
    """ZIP 파일명에서 차량 정보 추출 (URL 인코딩된 이름 지원)"""
    base_name = urllib.parse.unquote(zipname.replace(".zip", ""))
    match = re.search(r'^([^_]+)_(\d{4})_(.+)$', base_name)
    if match:
        return {
            "manufacturer": match.group(1),
            "year": match.group(2),
            "model": match.group(3).replace("_", " ")
        }
    return {}

def extract_text_from_html(html_content):
    """HTML에서 텍스트 추출"""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    return soup.get_text(separator='\n', strip=True)

def get_ollama_embedding(text):
    """Ollama API를 통해 텍스트 임베딩 생성 (재시도 포함)"""
    for attempt in range(1, EMBED_RETRIES + 1):
        try:
            response = requests.post(OLLAMA_API_URL, json={
                "model": MODEL_NAME,
                "input": text
            }, timeout=90)
            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings")
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                log(f"  [ERROR] Ollama response missing embeddings")
                return None
            log(f"  [ERROR] Ollama API Error: {response.status_code} (attempt {attempt}/{EMBED_RETRIES})")
        except Exception as e:
            log(f"  [ERROR] Embedding Error (attempt {attempt}/{EMBED_RETRIES}): {e}")
        if attempt < EMBED_RETRIES:
            time.sleep(EMBED_RETRY_DELAY)
    return None

def format_sql(content, metadata, embedding, content_hash):
    """SQL INSERT 문 생성"""
    emb_str = str(embedding)
    meta_str = json.dumps(metadata, ensure_ascii=False).replace("'", "''")
    content_esc = content.replace("'", "''")
    return f"INSERT INTO knowledge_vectors (content, metadata, embedding, content_hash) VALUES ('{content_esc}', '{meta_str}', '{emb_str}', '{content_hash}') ON CONFLICT (content_hash) DO NOTHING;\n"

def process_zip_file(zip_path, dry_run=False):
    """ZIP 파일 처리 (HTML 추출 -> 청킹 -> 임베딩). dry_run이면 API/파일 쓰기 없이 청크 수만 집계."""
    zipname = os.path.basename(zip_path)
    log(f"Processing {zipname}..." + (" (dry-run)" if dry_run else ""))
    
    vehicle_meta = extract_metadata_from_zipname(zipname)
    if not vehicle_meta:
        log(f"  [SKIP] Cannot extract metadata from {zipname}")
        return False
    
    context_header = f"[Vehicle: {vehicle_meta['manufacturer']} {vehicle_meta['year']} {vehicle_meta['model']}]\n"
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            html_files = [f for f in zf.namelist() if f.startswith('pages/') and f.endswith('.html')]
            if not html_files:
                html_files = [f for f in zf.namelist() if f.endswith('.html')]
            if not html_files:
                log(f"  [SKIP] No .html files found in {zipname}")
                return False
            
            log(f"  Found {len(html_files)} pages")
            success_count = 0
            sql_f = None if dry_run else open(OUTPUT_SQL_PATH, 'a', encoding='utf-8')
            try:
                for page_ord, html_file in enumerate(html_files):
                    page_match = re.search(r'pages/(\d+)\.html', html_file)
                    page_number = int(page_match.group(1)) if page_match else page_ord
                    try:
                        html_content = zf.read(html_file).decode('utf-8', errors='ignore')
                    except Exception as e:
                        log(f"  [ERROR] Cannot read {html_file}: {e}")
                        continue
                    text = extract_text_from_html(html_content)
                    cleaned_text = clean_text(text)
                    if not cleaned_text or len(cleaned_text) < 50:
                        continue
                    chunks = splitter.split_text(cleaned_text)
                    total_chunks = len(chunks)
                    for chunk_idx, chunk in enumerate(chunks):
                        if not chunk.strip():
                            continue
                        final_text = context_header + f"[Page: {page_number}]\n" + chunk
                        if dry_run:
                            success_count += 1
                            continue
                        embedding = get_ollama_embedding(final_text)
                        if not embedding:
                            continue
                        metadata = {
                            **vehicle_meta,
                            "page_number": page_number,
                            "chunk_index": chunk_idx,
                            "total_chunks_in_page": total_chunks,
                            "source_file": html_file,
                            "source_zip": zipname,
                            "chunk_method": "smart_recursive_v1"
                        }
                        content_hash = get_hash(f"{final_text}_{zipname}_{page_number}_{chunk_idx}")
                        sql_line = format_sql(final_text, metadata, embedding, content_hash)
                        sql_f.write(sql_line)
                        success_count += 1
                    if page_number % 100 == 0:
                        log(f"  Progress: Page {page_number} processed")
            finally:
                if sql_f is not None:
                    sql_f.close()
            log(f"  [FINISH] {zipname}: {success_count} chunks" + (" (dry-run)" if dry_run else " embedded"))
            return True
            
    except Exception as e:
        log(f"  [FATAL ERROR] {zipname}: {e}")
        return False

def main():
    global OUTPUT_SQL_PATH, LOG_FILE
    parser = argparse.ArgumentParser(description="Extract manual HTML from ZIPs, chunk, embed via Ollama, write knowledge_vectors seed SQL.")
    parser.add_argument("suffix", nargs="?", default="", help="병렬 처리용 접미사 (예: 1 -> seed_manual_chunks_1.sql)")
    parser.add_argument("--resume", action="store_true", help="이미 처리된 ZIP은 건너뜀 (logs/embed_manuals_processed.txt 기준)")
    parser.add_argument("--dry-run", action="store_true", help="Ollama 호출 및 SQL 쓰기 없이 청크 수만 집계")
    args = parser.parse_args()
    if args.suffix:
        suffix = f"_{args.suffix}"
        OUTPUT_SQL_PATH = f"db/seed_manual_chunks{suffix}.sql"
        LOG_FILE = f"logs/embed_manuals{suffix}.log"
        processed_list = f"logs/embed_manuals_processed{suffix}.txt"
    else:
        processed_list = PROCESSED_LIST_FILE

    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_SQL_PATH)), exist_ok=True)

    processed = set()
    if args.resume and os.path.exists(processed_list):
        with open(processed_list, "r", encoding="utf-8") as f:
            processed = {line.strip() for line in f if line.strip()}
        log(f"Resume: {len(processed)} ZIPs already processed, skipping.")

    if not args.dry_run and not os.path.exists(OUTPUT_SQL_PATH):
        with open(OUTPUT_SQL_PATH, "w", encoding="utf-8") as f:
            f.write("-- knowledge_vectors seed (768 dim, nomic-embed-text, smart chunking)\n\n")

    log("=" * 60)
    log(f"Manual Embedding Pipeline Started (Model: {MODEL_NAME})" + (" [DRY-RUN]" if args.dry_run else ""))
    log(f"Source: {SOURCE_DIR}")
    log("=" * 60)

    zip_files = [f for f in os.listdir(SOURCE_DIR) if f.endswith(".zip")]
    if args.resume:
        zip_files = [z for z in zip_files if z not in processed]
        log(f"ZIPs to process: {len(zip_files)} (skipped {len(processed)})")
    else:
        log(f"Found {len(zip_files)} ZIP files")

    for idx, zipname in enumerate(zip_files, 1):
        zip_path = os.path.join(SOURCE_DIR, zipname)
        log(f"\n[{idx}/{len(zip_files)}] Starting {zipname}")
        ok = process_zip_file(zip_path, dry_run=args.dry_run)
        if ok and not args.dry_run:
            with open(processed_list, "a", encoding="utf-8") as f:
                f.write(zipname + "\n")
        if not args.dry_run:
            time.sleep(2)
    log("=" * 60)
    log("All ZIP files processed!")
    log("=" * 60)


if __name__ == "__main__":
    main()
