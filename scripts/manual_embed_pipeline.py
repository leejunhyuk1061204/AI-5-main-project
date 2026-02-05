import os
import json
import hashlib
import time
import requests
import shutil
import sys
from datetime import datetime
from dotenv import load_dotenv
import re
import urllib.parse

# .env 파일 로드
load_dotenv()

# --- 설정 (기본값) ---
SOURCE_DIR = os.path.abspath("data/manuals/parsed")
DEST_DIR = os.path.abspath("data/manuals/embedded")
OUTPUT_SQL_PATH = "db/seed_knowledge_vectors.sql"
LOG_FILE = "logs/embed_pipeline.log"

# 명령행 인자가 있으면 (예: v1, v2, v3) 파일명에 추가
suffix = ""
if len(sys.argv) > 1:
    suffix = f"_{sys.argv[1]}"
    OUTPUT_SQL_PATH = f"db/seed_knowledge_vectors{suffix}.sql"
    LOG_FILE = f"logs/embed_pipeline{suffix}.log"

MODEL_NAME = "nomic-embed-text"  # 768차원, 고속 모델
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

def get_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def clean_text(text):
    if not text: return ""
    # 1. SQL 이스케이프 및 NULL 문자 제거
    text = text.replace('\x00', '').replace("'", "''")
    # 2. 제어 문자 제거 (줄바꿈/탭은 보존)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xad]', '', text)
    # 3. 과도한 공백 정규화 (3개 이상 줄바꿈 -> 2개로)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# --- Smart Chunking Logic (Recursive) ---
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
        # 1. Base case: Fits in chunk size
        if len(text) <= self.chunk_size:
            final_chunks.append(text)
            return

        # 2. Select separator
        separator = ""
        next_separators = []
        
        for i, sep in enumerate(separators):
            if sep in text:
                separator = sep
                next_separators = separators[i+1:]
                break
        
        # If no separator found (and text is too big), force split by char (fallback)
        if not separator and not next_separators:
             # Just hard split
             for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                 final_chunks.append(text[i:i+self.chunk_size])
             return

        # 3. Split
        # if separator is empty string (character split), split works differently
        if separator == "":
             splits = list(text)
        else:
             splits = text.split(separator)

        # 4. Process Splits (Merge small ones, recurse big ones)
        good_splits = []
        for s in splits:
            if separator != "": s = s.strip()
            if not s: continue
            
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if next_separators:
                    # Recurse on this big segment
                    sub_chunks = []
                    self._split_recursive(s, next_separators, sub_chunks)
                    good_splits.extend(sub_chunks)
                else:
                    # Should not happen given separators logic, but safe fallback
                    good_splits.append(s)

        # 5. Merge 'good_splits' into chunks with overlap
        self._merge_splits(good_splits, separator, final_chunks)

    def _merge_splits(self, splits, separator, final_chunks):
        current_doc = []
        current_len = 0
        
        for s in splits:
            s_len = len(s)
            sep_len = len(separator) if current_len > 0 else 0
            
            if current_len + s_len + sep_len > self.chunk_size:
                # Flush current chunk
                if current_doc:
                    chunk_text = separator.join(current_doc)
                    final_chunks.append(chunk_text)
                    
                    # Create Overlap for next chunk
                    # Keep trailing segments that fit in overlap
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


def get_ollama_embedding(text):
    """Ollama API를 통해 텍스트 임베딩 생성"""
    try:
        response = requests.post(OLLAMA_API_URL, json={
            "model": MODEL_NAME,
            "prompt": text
        }, timeout=90)
        
        if response.status_code == 200:
            return response.json().get("embedding")
        else:
            log(f"  [ERROR] Ollama API Error: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        log(f"  [ERROR] Ollama Timeout (90s)")
        return None
    except Exception as e:
        log(f"  [ERROR] Embedding Error: {e}")
        return None

def format_sql(content, metadata, embedding, content_hash):
    emb_str = str(embedding)
    meta_str = json.dumps(metadata).replace("'", "''")
    # content도 escape
    content_esc = content.replace("'", "''") 
    return f"INSERT INTO knowledge_vectors (content, metadata, embedding, content_hash) VALUES ('{content_esc}', '{meta_str}', '{emb_str}', '{content_hash}') ON CONFLICT (content_hash) DO NOTHING;\n"

def extract_metadata_from_filename(filename):
    """파일명에서 제조사, 연식, 모델명을 추출"""
    decoded_name = urllib.parse.unquote(filename)
    base_name = decoded_name.replace(".json", "").replace("_full", "")
    match = re.search(r'^([^_]+)_(\d{4})_(.+)$', base_name)
    
    if match:
        manufacturer = match.group(1)
        year = match.group(2)
        model_part = match.group(3)
        model_name = re.split(r'_(?:[LV]\d|Hybrid|Electric|AWD|FWD|Quattro)', model_part)[0]
        model_name = model_name.replace("_", " ").strip()
        
        return {
            "manufacturer": manufacturer,
            "year": year,
            "model_name": model_name
        }
    return {}

splitter = SmartTextSplitter(CHUNK_SIZE, CHUNK_OVERLAP)

def process_file(filepath):
    filename = os.path.basename(filepath)
    log(f"Starting Smart Embedding for {filename}...")
    
    file_metadata = extract_metadata_from_filename(filename)
    context_header = ""
    if file_metadata:
        context_header = f"[Context: {file_metadata.get('manufacturer')} {file_metadata.get('year')} {file_metadata.get('model_name')}]\n"

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            data_list = json.load(f)
            
        if not isinstance(data_list, list):
            log(f"  [SKIP] Invalid format.")
            return False

        success_count = 0
        error_count = 0
        
        with open(OUTPUT_SQL_PATH, 'a', encoding='utf-8') as sql_f:
            for item_idx, item in enumerate(data_list):
                raw_content = item.get("content", item.get("original_context", ""))
                # 먼저 Clean
                cleaned_content = clean_text(raw_content)
                if not cleaned_content: continue
                
                # Smart Splitting
                chunks = splitter.split_text(cleaned_content)
                
                for idx, chunk in enumerate(chunks):
                    if not chunk.strip(): continue
                    
                    # Context Injection
                    final_text = context_header + chunk
                    
                    embedding = get_ollama_embedding(final_text)
                    
                    if not embedding:
                        error_count += 1
                        continue
                    
                    metadata = {k: v for k, v in item.items() if k not in ["content", "original_context"]}
                    metadata.update(file_metadata)
                    metadata["source_file"] = filename
                    metadata["chunk_index"] = idx
                    metadata["chunk_method"] = "smart_recursive_v1"
                    
                    # Hash calculation (Include context header to be safe)
                    content_hash = get_hash(f"{final_text}_{filename}_{item_idx}_{idx}")
                    
                    sql_line = format_sql(final_text, metadata, embedding, content_hash)
                    sql_f.write(sql_line)
                    success_count += 1
                
                if item_idx % 50 == 0:
                    log(f"  Progress: {item_idx}/{len(data_list)} items processed (Success: {success_count})")

        log(f"  [FINISH] {filename}: Success {success_count} chunks")
        return True 
    except Exception as e:
        log(f"  [FATAL ERROR] {filename}: {e}")
        return False

def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_SQL_PATH)), exist_ok=True)
    
    if not os.path.exists(OUTPUT_SQL_PATH):
        with open(OUTPUT_SQL_PATH, 'w', encoding='utf-8') as f:
            f.write("-- Vector Knowledge Seed Data (Manuals - 768 Dim - Smart Chunking)\n\n")

    log("="*60)
    log(f"Smart Embedding Pipeline Started (Model: {MODEL_NAME})")
    log("="*60)

    while True:
        all_files = os.listdir(SOURCE_DIR)
        json_files = [f for f in all_files if f.endswith('.json')]
        
        if not json_files:
            # log("No files to process. Waiting...") # 로그 너무 많이 쌓임 방지
            time.sleep(60)
            continue
            
        json_files.sort()
        
        for file in json_files:
            src_path = os.path.join(SOURCE_DIR, file)
            processing_path = src_path + ".processing"
            
            if not os.path.exists(src_path):
                continue
                
            try:
                os.rename(src_path, processing_path)
                log(f"[LOCK] Acquired: {file}")
            except Exception:
                continue
                
            if process_file(processing_path):
                dest_path = os.path.join(DEST_DIR, file)
                try:
                    shutil.move(processing_path, dest_path)
                    log(f"[FINISH] Moved to {dest_path}")
                except Exception as e:
                    log(f"[ERROR] Move failed: {e}")
            else:
                os.rename(processing_path, src_path)
                log(f"[RETRY] Restored {file}")
                time.sleep(5)
                
        time.sleep(5)

if __name__ == "__main__":
    main()
