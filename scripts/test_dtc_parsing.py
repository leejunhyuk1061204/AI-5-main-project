import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"

def test_dtc_translation():
    texts = [
        "BARO Circuit Range Performance Malfunction",
        "BARO Circuit Low Input"
    ]
    combined_input = "\n".join([f"[{i}] {text}" for i, text in enumerate(texts)])
    prompt = f"Translate these automotive Diagnostic Trouble Code (DTC) descriptions into professional Korean. Keep it concise. Format as [index] Translation:\n\n{combined_input}"
    
    print(f"Testing DTC translation with {MODEL_NAME}...")
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
            result_text = response.json().get('response', '')
            print(f"Ollama Response:\n{result_text}\n")
            
            # 파싱 시도
            translated_lines = {}
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                match = re.search(r'\[?(\d+)\]?[\s\.\:]+(.*)', line)
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
