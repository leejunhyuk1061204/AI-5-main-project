import json
import requests
import os
import time

# --- 설정 ---
INPUT_FILE = "data/dtc/github_dtc_bulk.json"
OUTPUT_FILE = "data/dtc/github_dtc_bulk_ko.json"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3" # 사용자 환경에 따라 변경
BATCH_SIZE = 50 # 한 번에 처리할 개수

def translate_batch(texts):
    """Ollama를 사용하여 여러 DTC 설명을 한글로 번역"""
    combined_input = "\n".join([f"[{i}] {text}" for i, text in enumerate(texts)])
    prompt = f"Translate these automotive Diagnostic Trouble Code (DTC) descriptions into professional Korean. Keep it concise. Format as [index] Translation:\n\n{combined_input}"
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        if response.status_code == 200:
            result_text = response.json().get('response', '')
            # 파싱 로직 보완
            translated_lines = {}
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                # "[0] 번역내용" 또는 "0. 번역내용" 또는 "0번: 번역내용" 등 대응
                import re
                match = re.search(r'\[?(\d+)\]?[\s\.\:]+(.*)', line)
                if match:
                    try:
                        idx = int(match.group(1))
                        content = match.group(2).strip()
                        translated_lines[idx] = content
                    except:
                        continue
            
            # 만약 위 방식으로 파싱이 안 되었다면 줄 단위로 매칭 시도
            if not translated_lines:
                for i, line in enumerate(lines[:len(texts)]):
                    translated_lines[i] = line.strip()
                    
            return translated_lines
    except Exception as e:
        print(f"  [Batch Translation Error] {e}")
    return {}

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Total DTCs to translate: {len(data)}")
    
    # 이미 처리된 데이터가 있는지 확인 (재개 로직)
    start_index = 0
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                processed_data = json.load(f)
                start_index = len(processed_data)
                print(f"Resuming from index: {start_index}")
            except:
                processed_data = []
    else:
        processed_data = []

    for i in range(start_index, len(data), BATCH_SIZE):
        batch = data[i : i + BATCH_SIZE]
        texts = [item.get('original_context', '') for item in batch]
        
        print(f"Translating batch {i // BATCH_SIZE + 1} ({i}/{len(data)})...")
        translations = translate_batch(texts)
        
        for j, item in enumerate(batch):
            item['korean_description'] = translations.get(j, "")
            processed_data.append(item)
        
        # 중간 저장
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
            
        time.sleep(1) # 부하 조절

    print("DTC Translation Complete!")

if __name__ == "__main__":
    main()
