import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"

def test_ollama():
    print(f"Testing Ollama at {OLLAMA_URL} with model {MODEL_NAME}...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": "Say hello in Korean",
                "stream": False
            },
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json().get('response', '')}")
            return True
        else:
            print(f"Error Body: {response.text}")
    except Exception as e:
        print(f"Connection Error: {e}")
    return False

if __name__ == "__main__":
    test_ollama()
