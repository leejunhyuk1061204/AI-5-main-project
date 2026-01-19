import sys
import io
import requests
import re

# Windows 터미널 한글 깨짐 방지
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"

def test_dtc_translation():
    texts = [
        "BARO Circuit Range Performance Malfunction",
        "BARO Circuit Low Input"
    ]
    combined_input = "\n".join([f"[{i}] {text}" for i, text in enumerate(texts)])
    # 프롬프트 보강: 형식을 더 엄격하게 요청
    prompt = f"""Translate these automotive Diagnostic Trouble Code (DTC) descriptions into professional Korean.
Keep it concise and professional.
Output MUST follow this format for EACH line: [index] Translation

Texts to translate:
{combined_input}"""
    
    print(f"Testing DTC translation with {MODEL_NAME}...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3 # 일관성을 위해 낮은 온도로 설정
                }
            },
            timeout=30
        )
        if response.status_code == 200:
            result_text = response.json().get('response', '')
            print(f"Ollama Response:\n{result_text}\n")
            
            # 파싱 시도
            translated_lines = {}
            lines = result_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                # 다양한 패턴 지원 ([0], [0]:, 0., 0:)
                match = re.search(r'(?:\[?(\d+)\]?[\s\.\:]+)(.*)', line)
                if match:
                    idx = int(match.group(1))
                    content = match.group(2).strip()
                    translated_lines[idx] = content
            
            print(f"Parsed Results: {translated_lines}")
            return translated_lines
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Exception: {e}")
    return {}

if __name__ == "__main__":
    test_dtc_translation()
