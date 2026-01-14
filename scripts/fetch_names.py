import requests
from bs4 import BeautifulSoup
import urllib.parse

targets = [
    ("BMW", "2012"),
    ("Mercedes-Benz", "2012"),
    ("Audi", "2012"),
    ("Lexus", "2012"),
    ("Volkswagen", "2012"),
    ("Chevrolet", "2012"),
    ("Toyota", "2012"),
]

print("TARGETS_UPDATED = [")

for brand, year in targets:
    url = f"https://charm.li/{brand}/{year}/"
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            print(f"  # Error accessing {brand} {year}")
            continue
            
        soup = BeautifulSoup(r.text, 'html.parser')
        # charm.li lists models in a specific format. URLs are like /BMW/2012/Specific%20Model/
        # We need to extract 'Specific Model' part.
        
        # Helper to filter interesting models (simplified)
        keywords = ["328i", "528i", "X5", "750Li", 
                    "C250", "E350", "S550", "GLK350",
                    "A4", "A6", "Q5",
                    "ES 350", "RX 350", "ES350", "RX350",
                    "Tiguan", "Golf", "Passat",
                    "Spark", "Equinox",
                    "Camry", "Prius"]
        
        links = soup.find_all('a')
        found_models = set()
        
        for link in links:
            href = link.get('href')
            if href and href.startswith(f"https://charm.li/{brand}/{year}/"):
                # Extract model part: https://charm.li/Brand/Year/ModelName/
                # href might be relative or absolute. charm.li usually absolute in listings? 
                # Actually checking the chunk raw content, brackets are markdown: [Model Name](url)
                # If using BS4 on raw HTML, it's <ul><li><a href="...">Model Name</a></li></ul>
                
                parts = href.strip('/').split('/')
                # parts[-1] might be the model name encoded
                model_encoded = parts[-1]
                model_name = urllib.parse.unquote(model_encoded)
                
                # Filter by keywords
                if any(k in model_name for k in keywords):
                    # Clean up: sometimes charm.li has sub-models. 
                    # We want the folder name exactly as it appears in the URL.
                    # which is `model_encoded`.
                    
                    if model_name not in found_models:
                        print(f"    (\"{brand}\", \"{year}\", \"{model_encoded}\"), # {model_name}")
                        found_models.add(model_name)

    except Exception as e:
        print(f"  # Error: {e}")

print("]")
