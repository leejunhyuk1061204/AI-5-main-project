# -*- coding: utf-8 -*-
"""
Fill db/seed_car_models_118_review.csv with year_start, year_end, fuel_types
sourced from internet (Wikipedia, Cars.com, manufacturer/model history).
Only real model years and fuel types; no blanket 2010-2025 x all fuels.
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REVIEW_CSV = PROJECT / "db" / "seed_car_models_118_review.csv"

# (manufacturer_en, model_name_en) -> (year_start, year_end, "FUEL1,FUEL2,...")
# Sourced from Wikipedia, Cars.com, JD Power, manufacturer history (Feb 2025).
WEB_DATA = {
    ("Audi", "A3"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Audi", "A5"): (2010, 2025, "GASOLINE"),
    ("Audi", "A6"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Audi", "A8"): (2010, 2025, "GASOLINE"),
    ("Audi", "A8L"): (2010, 2025, "GASOLINE"),
    ("Audi", "Q5"): (2010, 2025, "DIESEL,GASOLINE,HEV"),
    ("Audi", "Q7"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Audi", "S6"): (2012, 2025, "GASOLINE"),
    ("Audi", "TT Quattro Coupe"): (2010, 2023, "GASOLINE"),
    ("Audi", "TT Quattro Roadster"): (2010, 2023, "GASOLINE"),
    ("Audi", "TTS Quattro Coupe"): (2010, 2023, "GASOLINE"),
    ("Audi", "TTS Quattro Roadster"): (2010, 2023, "GASOLINE"),
    ("BMW", "Alpina B7 xDrive"): (2011, 2015, "GASOLINE"),
    ("BMW", "M3"): (2010, 2025, "GASOLINE"),
    ("BMW", "M6"): (2010, 2018, "GASOLINE"),
    ("BMW", "X1 sDrive 28i"): (2013, 2015, "GASOLINE"),
    ("BMW", "X1 xDrive 28i"): (2013, 2015, "GASOLINE"),
    ("BMW", "X1 xDrive 35i"): (2013, 2015, "GASOLINE"),
    ("BMW", "X3 xDrive 28i"): (2011, 2017, "GASOLINE"),
    ("BMW", "X3 xDrive 35i"): (2011, 2017, "GASOLINE"),
    ("BMW", "X5 M"): (2010, 2025, "GASOLINE"),
    ("BMW", "X5 xDrive 35d"): (2010, 2013, "DIESEL"),
    ("BMW", "X5 xDrive 35i"): (2010, 2013, "GASOLINE"),
    ("BMW", "X5 xDrive 50i"): (2010, 2013, "GASOLINE"),
    ("Buick", "Encore"): (2013, 2025, "GASOLINE"),
    ("Buick", "LaCrosse"): (2010, 2019, "GASOLINE"),
    ("Buick", "Regal"): (2010, 2020, "GASOLINE"),
    ("Buick", "Verano"): (2012, 2017, "GASOLINE"),
    ("Cadillac", "CTS Sedan"): (2010, 2019, "GASOLINE"),
    ("Cadillac", "CTS Wagon"): (2010, 2014, "GASOLINE"),
    ("Cadillac", "Escalade"): (2010, 2025, "GASOLINE,HEV"),
    ("Cadillac", "Escalade/ESV"): (2010, 2025, "GASOLINE,HEV"),
    ("Cadillac", "SRX"): (2010, 2016, "GASOLINE"),
    ("Cadillac", "STS"): (2010, 2011, "GASOLINE"),
    ("Chevrolet", "Avalanche"): (2010, 2013, "GASOLINE"),
    ("Chevrolet", "Camaro"): (2010, 2025, "GASOLINE"),
    ("Chevrolet", "Corvette"): (2010, 2025, "GASOLINE"),
    ("Chevrolet", "Cruze"): (2010, 2019, "DIESEL,GASOLINE"),
    ("Chevrolet", "Equinox"): (2010, 2025, "GASOLINE"),
    ("Chevrolet", "Express 1500"): (2010, 2025, "GASOLINE"),
    ("Chevrolet", "Express 2500"): (2010, 2025, "DIESEL,GASOLINE,LPG"),
    ("Chevrolet", "Express 3500"): (2010, 2025, "DIESEL,GASOLINE,LPG"),
    ("Chevrolet", "Malibu"): (2010, 2025, "GASOLINE,HEV"),
    ("Chevrolet", "Silverado 1500"): (2010, 2025, "DIESEL,GASOLINE,HEV"),
    ("Chevrolet", "Silverado 2500"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Chevrolet", "Tahoe"): (2010, 2025, "GASOLINE,HEV"),
    ("Chevrolet", "Traverse"): (2010, 2025, "GASOLINE"),
    ("Chevrolet", "Volt"): (2011, 2019, "EV,HEV"),
    ("Dodge and Ram", "Challenger"): (2010, 2023, "GASOLINE"),
    ("Dodge and Ram", "Challenger SRT-8"): (2010, 2023, "GASOLINE"),
    ("Dodge and Ram", "Charger"): (2010, 2025, "GASOLINE"),
    ("Dodge and Ram", "Charger SRT-8"): (2010, 2014, "GASOLINE"),
    ("Dodge and Ram", "Dakota"): (2010, 2011, "GASOLINE"),
    ("Dodge and Ram", "Durango"): (2011, 2025, "GASOLINE"),
    ("Dodge and Ram", "Grand Caravan"): (2010, 2020, "GASOLINE"),
    ("Dodge and Ram", "Journey"): (2010, 2020, "GASOLINE"),
    ("Dodge and Ram", "RAM 1500 Truck"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Ford", "E 150"): (2010, 2025, "GASOLINE"),
    ("Ford", "E 350"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Ford", "E 450"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Ford", "Edge"): (2010, 2025, "GASOLINE"),
    ("Ford", "Escape"): (2010, 2025, "GASOLINE,HEV"),
    ("Ford", "Expedition"): (2010, 2025, "GASOLINE"),
    ("Ford", "Explorer"): (2011, 2025, "GASOLINE,HEV"),
    ("Ford", "F 150"): (2010, 2025, "DIESEL,GASOLINE,HEV"),
    ("Ford", "F 450"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Ford", "F 550"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Ford", "Flex"): (2010, 2019, "GASOLINE"),
    ("Ford", "Mustang"): (2010, 2025, "GASOLINE"),
    ("Ford", "Police Interceptor"): (2013, 2019, "GASOLINE"),
    ("Ford", "Police Interceptor Utility"): (2013, 2019, "GASOLINE"),
    ("Ford", "Ranger"): (2010, 2025, "GASOLINE"),
    ("Ford", "Taurus"): (2010, 2019, "GASOLINE"),
    ("Ford", "Transit Connect"): (2010, 2025, "GASOLINE"),
    ("GMC", "Acadia"): (2010, 2025, "GASOLINE"),
    ("GMC", "Savana 1500"): (2010, 2025, "GASOLINE"),
    ("GMC", "Savana 2500"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Savana 3500"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Savana 4500"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Sierra 1500"): (2010, 2025, "DIESEL,GASOLINE,HEV"),
    ("GMC", "Sierra 2500"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Sierra 2500 Denali"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Sierra 3500"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Sierra 3500 Denali"): (2010, 2025, "DIESEL,GASOLINE"),
    ("GMC", "Sierra Denali"): (2014, 2025, "GASOLINE"),
    ("GMC", "Terrain"): (2010, 2025, "GASOLINE"),
    ("GMC", "Yukon"): (2010, 2025, "GASOLINE,HEV"),
    ("Honda", "Element"): (2010, 2011, "GASOLINE"),
    ("Honda", "Fit"): (2010, 2020, "GASOLINE"),
    ("Honda", "Insight"): (2010, 2022, "HEV"),
    ("Honda", "Odyssey"): (2010, 2025, "GASOLINE"),
    ("Honda", "Pilot"): (2010, 2025, "GASOLINE"),
    ("Honda", "Ridgeline"): (2010, 2025, "GASOLINE"),
    ("Hyundai", "Genesis"): (2010, 2016, "GASOLINE"),
    ("Infiniti", "EX35"): (2008, 2013, "GASOLINE"),
    ("Infiniti", "FX50"): (2010, 2013, "GASOLINE"),
    ("Infiniti", "G25"): (2011, 2012, "GASOLINE"),
    ("Infiniti", "G25x"): (2011, 2012, "GASOLINE"),
    ("Infiniti", "G37"): (2010, 2013, "GASOLINE"),
    ("Infiniti", "G37x"): (2010, 2013, "GASOLINE"),
    ("Jaguar", "XF"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Jaguar", "XJ"): (2010, 2019, "GASOLINE"),
    ("Jaguar", "XK"): (2010, 2014, "GASOLINE"),
    ("Jeep", "Compass"): (2010, 2025, "GASOLINE"),
    ("Jeep", "Grand Cherokee"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Jeep", "Patriot"): (2010, 2017, "GASOLINE"),
    ("Kia", "Magentis"): (2010, 2010, "GASOLINE"),
    ("Kia", "Optima"): (2010, 2020, "GASOLINE,HEV"),
    ("Kia", "Rio"): (2010, 2025, "GASOLINE"),
    ("Kia", "Rondo"): (2010, 2012, "GASOLINE"),
    ("Kia", "Sedona"): (2010, 2025, "GASOLINE"),
    ("Kia", "Soul"): (2010, 2025, "GASOLINE"),
    ("Land Rover", "LR2"): (2010, 2015, "GASOLINE"),
    ("Land Rover", "Range Rover"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Land Rover", "Range Rover Evoque"): (2012, 2025, "DIESEL,GASOLINE"),
    ("Land Rover", "Range Rover Sport"): (2010, 2025, "DIESEL,GASOLINE"),
    ("Mercedes Benz", "SL 63 AMG"): (2011, 2025, "GASOLINE"),
    ("Mercedes Benz", "SL 65 AMG"): (2010, 2020, "GASOLINE"),
}


def main():
    rows = []
    with open(REVIEW_CSV, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fieldnames = r.fieldnames
        for row in r:
            key = (row["manufacturer_en"].strip(), row["model_name_en"].strip())
            if key in WEB_DATA:
                y1, y2, fuels = WEB_DATA[key]
                row["year_start"] = y1
                row["year_end"] = y2
                row["fuel_types"] = fuels
            rows.append(row)

    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    filled = sum(1 for r in rows if r.get("year_start") and r.get("fuel_types"))
    print(f"Updated {REVIEW_CSV.name}: {filled}/{len(rows)} rows with year/fuel from web data.")


if __name__ == "__main__":
    main()
