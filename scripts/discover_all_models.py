import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import json

# Targets to search
years = ["2010", "2011", "2012", "2013"]
brands = [
    "Acura", "Audi", "BMW", "Buick", "Cadillac", "Chevrolet", "Chrysler", 
    "Dodge and Ram", "Fiat", "Ford", "GMC", "Honda", "Hummer", "Hyundai", 
    "Infiniti", "Isuzu", "Jaguar", "Jeep", "Kia", "Land Rover", "Lexus", 
    "Lincoln", "Mazda", "Mercedes Benz", "Mini", "Mitsubishi", "Nissan-Datsun", 
    "Pontiac", "Porsche", "Saab", "Saturn", "Scion", "Smart", "Subaru", 
    "Suzuki", "Toyota", "Volkswagen", "Volvo"
]

all_discovered = []

print(f"Starting discovery for {len(brands)} brands across {len(years)} years...")

for brand in brands:
    print(f"Searching {brand}...")
    brand_encoded = brand.replace(" ", "%20")
    for year in years:
        url = f"https://charm.li/{brand_encoded}/{year}/"
        try:
            time.sleep(0.5) # Be respectful
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                links = soup.find_all('a')
                
                count = 0
                for link in links:
                    href = link.get('href')
                    # Expecting href to be like /{brand}/{year}/{model}/
                    if href and f"/{brand_encoded}/{year}/" in href:
                        parts = href.strip('/').split('/')
                        if len(parts) >= 3:
                            model_encoded = parts[-1]
                            model_name = urllib.parse.unquote(model_encoded)
                            
                            # Avoid generic links like 'Repair and Diagnosis'
                            if model_name.lower() in ["home", "about", brand.lower(), year]:
                                continue
                                
                            all_discovered.append({
                                "brand": brand,
                                "year": year,
                                "model": model_encoded,
                                "model_name": model_name
                            })
                            count += 1
                # print(f"  - {year}: Found {count} models")
            else:
                pass
        except Exception as e:
            # print(f"  - {year}: Error {e}")
            pass

# Save results
output_path = "data/manuals/all_discovered_targets.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(all_discovered, f, ensure_ascii=False, indent=2)

print(f"\nDiscovery Complete! Total models found: {len(all_discovered)}")
print(f"Results saved to {output_path}")
