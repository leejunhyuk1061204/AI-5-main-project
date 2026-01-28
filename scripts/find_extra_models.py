import requests
from bs4 import BeautifulSoup
import urllib.parse
import time

# Targets to search (Brand, Year)
search_queries = []
years = ["2010", "2011", "2012", "2013"]
brands = [
    "Nissan", "Toyota", "Honda", "Ford", "Chrysler", 
    "Jeep", "Lincoln", "Jaguar", "Peugeot", "Mini", "Lexus", "Volkswagen"
]

for b in brands:
    for y in years:
        search_queries.append((b, y))

# Keywords for popular models in Korea
keywords = [
    # Nissan
    "Altima", "Maxima", "Murano", "Rogue", "Sentra",
    # Toyota
    "Camry", "Prius", "Sienna", "RAV4", "Corolla", "Avalon",
    # Honda
    "Accord", "Civic", "CR-V", "Odyssey", "Pilot",
    # Ford
    "Explorer", "Taurus", "Fusion", "Focus", "Mustang", "Escape",
    # Chrysler
    "300", "Town", "Sebring", "200",
    # Jeep
    "Wrangler", "Compass", 
    # Lincoln
    "MKZ", "MKS", "MKX",
    # Jaguar
    "XF", "XJ", "XK",
    # Peugeot
    "207", "308", "3008", "508", "RCZ",
    # Mini
    "Cooper", "Countryman",
    # Lexus
    "IS 250", "IS250", "GS 350", "GS350", "LS 460", "LS460",
    # VW
    "CC", "Phaeton", "Beetle", "Passat", "Golf", "Jetta", "Tiguan", "Touareg"
]

print("EXTRA_TARGETS = [")

for brand, year in search_queries:
    url = f"https://charm.li/{brand}/{year}/"
    try:
        # random delay to be nice
        time.sleep(0.3)
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.find_all('a')
            
            found_for_brand_year = set()
            
            for link in links:
                href = link.get('href')
                if href and (f"/{brand}/{year}/" in href):
                    parts = href.strip('/').split('/')
                    model_encoded = parts[-1]
                    model_name = urllib.parse.unquote(model_encoded)
                    
                    # Filtering
                    if any(k in model_name for k in keywords):
                        # Avoid duplicates for same brand/year
                        if model_name not in found_for_brand_year:
                             print(f"    (\"{brand.replace('%20', ' ')}\", \"{year}\", \"{model_encoded}\"), # {model_name}")
                             found_for_brand_year.add(model_name)
        else:
            # print(f"  # Failed to access {brand} {year}: {r.status_code}")
            pass
            
    except Exception as e:
        # print(f"  # Error {brand} {year}: {e}")
        pass

print("]")
