import requests
import json

def test_embedding(text):
    url = "http://localhost:11434/api/embeddings"
    payload = {
        "model": "mxbai-embed-large",
        "prompt": text
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        print(f"Text Length: {len(text)}")
        print(f"Status Code: {r.status_code}")
        if r.status_code != 200:
            print(f"Error: {r.text}")
        else:
            emb = r.json().get("embedding", [])
            print(f"Embedding Dimensions: {len(emb)}")
    except Exception as e:
        print(f"Exception: {e}")

print("--- Test 1: Small string ---")
test_embedding("Hello world")

print("\n--- Test 2: 500 characters ---")
test_embedding("A" * 500)

print("\n--- Test 3: Problematic string (preview) ---")
test_embedding("About Operation CHARM, the free Collection of High Quality Automotive Repair Manuals. Repair manuals, or technical manuals, provide detailed instructions for maintaining, repairing, and servicing vehicles. They are essential tools for mechanics, technicians, and car enthusiasts who want to perform their own repairs. Historically, these manuals were only available in printed form and were often very expensive. However, with the rise of the internet, many repair manuals are now available online.")
