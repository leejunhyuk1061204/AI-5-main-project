import json
import re
from collections import Counter
import os

# DTC 데이터 경로
BULK_FILE = "data/dtc/github_dtc_bulk.json"
SUMMARY_FILE = "data/dtc/batch_dtc_summary.json"

def extract_words_and_phrases(text):
    """텍스트에서 단어와 구문 추출"""
    words = []
    
    # 전체 텍스트를 단어로 분리
    tokens = re.findall(r'[A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z0-9]*)*', text)
    
    for token in tokens:
        # 개별 단어
        for word in token.split():
            if len(word) >= 2:
                words.append(word)
        
        # 2-3 단어 구문
        parts = token.split()
        for i in range(len(parts)):
            if i + 1 < len(parts):
                words.append(f"{parts[i]} {parts[i+1]}")
            if i + 2 < len(parts):
                words.append(f"{parts[i]} {parts[i+1]} {parts[i+2]}")
    
    return words

def main():
    all_words = []
    
    # Bulk 파일 처리
    if os.path.exists(BULK_FILE):
        print(f"Processing {BULK_FILE}...")
        with open(BULK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            text = item.get('original_context', '')
            all_words.extend(extract_words_and_phrases(text))
    
    # Summary 파일 처리
    if os.path.exists(SUMMARY_FILE):
        print(f"Processing {SUMMARY_FILE}...")
        with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            text = item.get('original_context', '') + ' ' + item.get('title', '')
            all_words.extend(extract_words_and_phrases(text))
    
    # 빈도 계산
    counter = Counter(all_words)
    
    # 상위 500개 추출 (자동차 관련 용어가 자주 등장할 것)
    print("\n=== Top 500 Terms (sorted by frequency) ===\n")
    
    # 단일 단어와 구문 분리
    single_words = [(w, c) for w, c in counter.most_common(1000) if ' ' not in w and c >= 10]
    phrases = [(w, c) for w, c in counter.most_common(1000) if ' ' in w and c >= 5]
    
    print("--- Single Words (Top 200, freq >= 10) ---")
    for word, count in single_words[:200]:
        print(f"{word}: {count}")
    
    print("\n--- Phrases (Top 200, freq >= 5) ---")
    for phrase, count in phrases[:200]:
        print(f"{phrase}: {count}")

if __name__ == "__main__":
    main()
