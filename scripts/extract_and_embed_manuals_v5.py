"""
매뉴얼 ZIP → 풀기 → 청킹 → 임베딩 → knowledge_vectors 시드 SQL (v5).
리스트 6분할 중 5번: 원본_zip 목록 정렬 후 인덱스 % 6 == 4 인 ZIP만 처리.
작업: embedding작업 폴더에 풀고, 처리 후 해당 폴더 삭제. 시드: seed 폴더에 seed_v5.sql.
"""
import argparse
import os
import json
import hashlib
import time
import shutil
import urllib.parse
import requests
import zipfile
import re
from datetime import datetime
from bs4 import BeautifulSoup
from pathlib import Path

# --- 버전/리스트 (v5 = 5번 리스트) ---
VERSION = "v5"
LIST_INDEX = 4
NUM_LISTS = 6

# --- 경로 ---
SOURCE_DIR = r"G:\내 드라이브\정비지침서\원본_zip"
EXTRACT_DIR = r"G:\내 드라이브\정비지침서\embedding작업"
SEED_DIR = r"G:\내 드라이브\정비지침서\seed"

OUTPUT_SQL_PATH = os.path.join(SEED_DIR, f"seed_{VERSION}.sql")
LOG_FILE = f"logs/embed_manuals_{VERSION}.log"
PROCESSED_LIST_FILE = f"logs/embed_manuals_processed_{VERSION}.txt"

MODEL_NAME = "nomic-embed-text"
OLLAMA_API_URL = "http://localhost:11434/api/embed"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_RETRIES = 3
EMBED_RETRY_DELAY = 5


def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")


def get_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_text(text):
    if not text:
        return ""
    text = text.replace("\x00", "").replace("'", "''")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xad]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class SmartTextSplitter:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
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
                next_separators = separators[i + 1 :]
                break
        if not separator and not next_separators:
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                final_chunks.append(text[i : i + self.chunk_size])
            return
        if separator == "":
            splits = list(text)
        else:
            splits = text.split(separator)
        good_splits = []
        for s in splits:
            if separator != "":
                s = s.strip()
            if not s:
                continue
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
    base_name = urllib.parse.unquote(zipname.replace(".zip", ""))
    match = re.search(r"^([^_]+)_(\d{4})_(.+)$", base_name)
    if match:
        return {
            "manufacturer": match.group(1),
            "year": match.group(2),
            "model": match.group(3).replace("_", " "),
        }
    return {}


def extract_text_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def get_ollama_embedding(text):
    for attempt in range(1, EMBED_RETRIES + 1):
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json={"model": MODEL_NAME, "input": text},
                timeout=90,
            )
            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings")
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                log("  [ERROR] Ollama response missing embeddings")
                return None
            log(f"  [ERROR] Ollama API Error: {response.status_code} (attempt {attempt}/{EMBED_RETRIES})")
        except Exception as e:
            log(f"  [ERROR] Embedding Error (attempt {attempt}/{EMBED_RETRIES}): {e}")
        if attempt < EMBED_RETRIES:
            time.sleep(EMBED_RETRY_DELAY)
    return None


def format_sql(content, metadata, embedding, content_hash):
    emb_str = str(embedding)
    meta_str = json.dumps(metadata, ensure_ascii=False).replace("'", "''")
    content_esc = content.replace("'", "''")
    return f"INSERT INTO knowledge_vectors (content, metadata, embedding, content_hash) VALUES ('{content_esc}', '{meta_str}', '{emb_str}', '{content_hash}') ON CONFLICT (content_hash) DO NOTHING;\n"


def _collect_html_paths(extract_root):
    """풀린 디렉터리에서 HTML 경로 수집. pages/*.html 우선, 숫자 순 정렬."""
    paths = []
    for root, _, files in os.walk(extract_root):
        for f in files:
            if f.endswith(".html"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, extract_root).replace("\\", "/")
                paths.append((full, rel))
    pages_first = [p for p in paths if p[1].startswith("pages/")]
    others = [p for p in paths if p not in pages_first]
    if pages_first:
        def sort_key(x):
            m = re.search(r"pages/(\d+)\.html", x[1])
            return (0, int(m.group(1))) if m else (1, x[1])
        pages_first.sort(key=sort_key)
        return [p[0] for p in pages_first] + [p[0] for p in sorted(others, key=lambda x: x[1])]
    return [p[0] for p in sorted(paths, key=lambda x: x[1])]


def process_zip_file(zip_path, dry_run=False):
    zipname = os.path.basename(zip_path)
    zip_stem = zipname.replace(".zip", "")
    log(f"Processing {zipname}..." + (" (dry-run)" if dry_run else ""))

    vehicle_meta = extract_metadata_from_zipname(zipname)
    if not vehicle_meta:
        log(f"  [SKIP] Cannot extract metadata from {zipname}")
        return False

    context_header = f"[Vehicle: {vehicle_meta['manufacturer']} {vehicle_meta['year']} {vehicle_meta['model']}]\n"
    extract_root = os.path.join(EXTRACT_DIR, zip_stem)

    try:
        os.makedirs(EXTRACT_DIR, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_root)

        html_paths = _collect_html_paths(extract_root)
        if not html_paths:
            log(f"  [SKIP] No .html files in {zipname}")
            shutil.rmtree(extract_root, ignore_errors=True)
            return False

        log(f"  Found {len(html_paths)} pages")
        success_count = 0
        sql_f = None if dry_run else open(OUTPUT_SQL_PATH, "a", encoding="utf-8")
        try:
            for page_ord, html_full in enumerate(html_paths):
                rel_path = os.path.relpath(html_full, extract_root).replace("\\", "/")
                page_match = re.search(r"pages/(\d+)\.html", rel_path)
                page_number = int(page_match.group(1)) if page_match else page_ord
                try:
                    with open(html_full, "r", encoding="utf-8", errors="ignore") as f:
                        html_content = f.read()
                except Exception as e:
                    log(f"  [ERROR] Cannot read {rel_path}: {e}")
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
                        "source_file": rel_path,
                        "source_zip": zipname,
                        "chunk_method": "smart_recursive_v1",
                    }
                    content_hash = get_hash(f"{final_text}_{zipname}_{page_number}_{chunk_idx}")
                    sql_f.write(format_sql(final_text, metadata, embedding, content_hash))
                    success_count += 1
                if page_number % 100 == 0:
                    log(f"  Progress: Page {page_number} processed")
        finally:
            if sql_f is not None:
                sql_f.close()

        shutil.rmtree(extract_root, ignore_errors=True)
        log(f"  [FINISH] {zipname}: {success_count} chunks" + (" (dry-run)" if dry_run else " embedded"))
        return True

    except Exception as e:
        log(f"  [FATAL ERROR] {zipname}: {e}")
        if os.path.isdir(extract_root):
            shutil.rmtree(extract_root, ignore_errors=True)
        return False


def main():
    parser = argparse.ArgumentParser(description=f"Manual embedding pipeline {VERSION} (list index % {NUM_LISTS} == {LIST_INDEX})")
    parser.add_argument("--resume", action="store_true", help="이미 처리된 ZIP 건너뜀")
    parser.add_argument("--dry-run", action="store_true", help="풀기/청킹만, API·SQL 쓰기 없음")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    os.makedirs(SEED_DIR, exist_ok=True)

    processed = set()
    if args.resume and os.path.exists(PROCESSED_LIST_FILE):
        with open(PROCESSED_LIST_FILE, "r", encoding="utf-8") as f:
            processed = {line.strip() for line in f if line.strip()}
        log(f"Resume: {len(processed)} ZIPs already processed, skipping.")

    if not args.dry_run and not os.path.exists(OUTPUT_SQL_PATH):
        with open(OUTPUT_SQL_PATH, "w", encoding="utf-8") as f:
            f.write("-- knowledge_vectors seed (768 dim, nomic-embed-text, smart chunking)\n\n")

    all_zips = sorted([f for f in os.listdir(SOURCE_DIR) if f.endswith(".zip")])
    zip_files = [z for i, z in enumerate(all_zips) if i % NUM_LISTS == LIST_INDEX]
    if args.resume:
        zip_files = [z for z in zip_files if z not in processed]
    log("=" * 60)
    log(f"Pipeline {VERSION} Started (Model: {MODEL_NAME})" + (" [DRY-RUN]" if args.dry_run else ""))
    log(f"Source: {SOURCE_DIR} | Seed: {OUTPUT_SQL_PATH} | Extract: {EXTRACT_DIR}")
    log(f"ZIPs for this list: {len(zip_files)}" + (f" (skipped {len(processed)})" if args.resume else ""))
    log("=" * 60)

    for idx, zipname in enumerate(zip_files, 1):
        zip_path = os.path.join(SOURCE_DIR, zipname)
        log(f"\n[{idx}/{len(zip_files)}] Starting {zipname}")
        ok = process_zip_file(zip_path, dry_run=args.dry_run)
        if ok and not args.dry_run:
            with open(PROCESSED_LIST_FILE, "a", encoding="utf-8") as f:
                f.write(zipname + "\n")
        if not args.dry_run:
            time.sleep(2)
    log("=" * 60)
    log("Done.")
    log("=" * 60)


if __name__ == "__main__":
    main()
