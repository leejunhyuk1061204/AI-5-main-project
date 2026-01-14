# -*- coding: utf-8 -*-
import sys

# Define models with specific generations for better accuracy
# Structure: Manufacturer, Model Name (Code), Start Year, End Year, Fuel Types
# Note: Ranges are inclusive of start, exclusive of end in Python, so end year + 1
# Years here are roughly aligned with Korean market release.

data = [
    # === Hyundai ===
    # Avante (Elantra)
    ("Hyundai", "Avante (MD)", 2010, 2015, ["GASOLINE", "LPG", "DIESEL"]),
    ("Hyundai", "Avante (AD)", 2015, 2020, ["GASOLINE", "LPG", "DIESEL"]),
    ("Hyundai", "Avante (CN7)", 2020, 2025, ["GASOLINE", "LPG", "HEV"]), # Diesel dropped, HEV added

    # Sonata
    ("Hyundai", "Sonata (YF)", 2010, 2014, ["GASOLINE", "LPG", "HEV"]),
    ("Hyundai", "Sonata (LF)", 2014, 2019, ["GASOLINE", "LPG", "DIESEL", "HEV", "PHEV"]),
    ("Hyundai", "Sonata (DN8)", 2019, 2025, ["GASOLINE", "LPG", "HEV"]),

    # Grandeur (Azera)
    ("Hyundai", "Grandeur (HG)", 2011, 2016, ["GASOLINE", "DIESEL", "HEV", "LPG"]),
    ("Hyundai", "Grandeur (IG)", 2016, 2019, ["GASOLINE", "DIESEL", "HEV", "LPG"]),
    ("Hyundai", "Grandeur (IG FL)", 2019, 2022, ["GASOLINE", "HEV", "LPG"]),
    ("Hyundai", "Grandeur (GN7)", 2022, 2025, ["GASOLINE", "HEV", "LPG"]),

    # SUV
    ("Hyundai", "Tucson (ix)", 2010, 2015, ["DIESEL", "GASOLINE"]),
    ("Hyundai", "Tucson (TL)", 2015, 2020, ["DIESEL", "GASOLINE"]),
    ("Hyundai", "Tucson (NX4)", 2020, 2025, ["DIESEL", "GASOLINE", "HEV"]),
    
    ("Hyundai", "Santa Fe (CM)", 2010, 2012, ["DIESEL"]),
    ("Hyundai", "Santa Fe (DM)", 2012, 2018, ["DIESEL", "GASOLINE"]),
    ("Hyundai", "Santa Fe (TM)", 2018, 2023, ["DIESEL", "GASOLINE"]),
    ("Hyundai", "Santa Fe (MX5)", 2023, 2025, ["GASOLINE", "HEV"]),

    ("Hyundai", "Palisade", 2018, 2025, ["DIESEL", "GASOLINE"]),
    ("Hyundai", "Casper", 2021, 2025, ["GASOLINE"]),
    ("Hyundai", "Kona (OS)", 2017, 2023, ["GASOLINE", "DIESEL", "HEV", "EV"]),
    ("Hyundai", "Kona (SX2)", 2023, 2025, ["GASOLINE", "HEV", "EV"]),
    ("Hyundai", "Staria", 2021, 2025, ["DIESEL", "LPG", "HEV"]),
    ("Hyundai", "Starex (Grand)", 2010, 2021, ["DIESEL", "LPG"]),
    
    # EV Dedicated
    ("Hyundai", "Ioniq 5", 2021, 2025, ["EV"]),
    ("Hyundai", "Ioniq 6", 2022, 2025, ["EV"]),

    # === Kia ===
    # K Series
    ("Kia", "K3 (YD)", 2012, 2018, ["GASOLINE", "DIESEL"]),
    ("Kia", "K3 (BD)", 2018, 2025, ["GASOLINE"]),

    ("Kia", "K5 (TF)", 2010, 2015, ["GASOLINE", "LPG", "HEV"]),
    ("Kia", "K5 (JF)", 2015, 2019, ["GASOLINE", "LPG", "DIESEL", "HEV"]),
    ("Kia", "K5 (DL3)", 2019, 2025, ["GASOLINE", "LPG", "HEV"]),

    ("Kia", "K7 (VG)", 2010, 2011, ["GASOLINE", "LPG"]),
    ("Kia", "K7 (VG)", 2011, 2016, ["GASOLINE", "LPG", "HEV"]), # Hybrid added
    ("Kia", "K7 (YG)", 2016, 2021, ["GASOLINE", "DIESEL", "LPG", "HEV"]),
    ("Kia", "K8 (GL3)", 2021, 2025, ["GASOLINE", "LPG", "HEV"]),

    # SUV / RV
    ("Kia", "Sportage (SL)", 2010, 2015, ["DIESEL", "GASOLINE"]),
    ("Kia", "Sportage (QL)", 2015, 2021, ["DIESEL", "GASOLINE"]),
    ("Kia", "Sportage (NQ5)", 2021, 2025, ["DIESEL", "GASOLINE", "HEV", "LPG"]),

    ("Kia", "Sorento (R)", 2010, 2014, ["DIESEL", "GASOLINE"]),
    ("Kia", "Sorento (UM)", 2014, 2020, ["DIESEL", "GASOLINE"]),
    ("Kia", "Sorento (MQ4)", 2020, 2025, ["DIESEL", "GASOLINE", "HEV"]),

    ("Kia", "Carnival (R)", 2010, 2014, ["DIESEL", "GASOLINE"]),
    ("Kia", "Carnival (YP)", 2014, 2020, ["DIESEL", "GASOLINE"]),
    ("Kia", "Carnival (KA4)", 2020, 2025, ["DIESEL", "GASOLINE", "HEV"]),
    
    ("Kia", "Niro (DE)", 2016, 2022, ["HEV", "PHEV", "EV"]),
    ("Kia", "Niro (SG2)", 2022, 2025, ["HEV", "EV"]),
    ("Kia", "Seltos", 2019, 2025, ["GASOLINE", "DIESEL"]),

    ("Kia", "Ray", 2011, 2025, ["GASOLINE", "EV"]), # EV exists in early models too

    # EV Dedicated
    ("Kia", "EV6", 2021, 2025, ["EV"]),
    ("Kia", "EV9", 2023, 2025, ["EV"]),

    # === Genesis ===
    ("Genesis", "G70", 2017, 2025, ["GASOLINE", "DIESEL"]),
    ("Genesis", "G80 (DH)", 2016, 2020, ["GASOLINE", "DIESEL"]),
    ("Genesis", "G80 (RG3)", 2020, 2025, ["GASOLINE", "DIESEL", "EV"]),
    ("Genesis", "G90", 2016, 2025, ["GASOLINE"]),
    ("Genesis", "GV60", 2021, 2025, ["EV"]),
    ("Genesis", "GV70", 2020, 2025, ["GASOLINE", "DIESEL", "EV"]),
    ("Genesis", "GV80", 2020, 2025, ["GASOLINE", "DIESEL"]),

    # === KG Mobility (SsangYong) ===
    ("KG Mobility", "Tivoli", 2015, 2025, ["GASOLINE", "DIESEL"]),
    ("KG Mobility", "Torres", 2022, 2025, ["GASOLINE", "EV"]),
    ("KG Mobility", "Korando", 2011, 2025, ["DIESEL", "GASOLINE", "EV"]),
    ("KG Mobility", "Rexton", 2010, 2025, ["DIESEL", "GASOLINE"]),

    # === Renault Korea (Samsung) ===
    ("Renault Korea", "SM6", 2016, 2025, ["GASOLINE", "DIESEL", "LPG"]),
    ("Renault Korea", "QM6", 2016, 2025, ["GASOLINE", "DIESEL", "LPG"]),
    ("Renault Korea", "XM3", 2020, 2025, ["GASOLINE", "HEV"]),
    ("Renault Korea", "SM5 (Nova)", 2010, 2019, ["GASOLINE", "DIESEL", "LPG"]),

    # === Chevrolet ===
    ("Chevrolet", "Spark", 2011, 2023, ["GASOLINE"]),
    ("Chevrolet", "Trax", 2013, 2025, ["GASOLINE", "DIESEL"]),
    ("Chevrolet", "Trailblazer", 2020, 2025, ["GASOLINE"]),
]

output_file = "db/seed_car_models.sql"

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('-- Auto-generated Seed Data for car_model_master\n')
    f.write('-- Contains popular Korean models with generation-based fuel type mapping\n')
    f.write('INSERT INTO car_model_master (manufacturer, model_name, model_year, fuel_type) VALUES\n')

    values = []
    for brand, model, start_year, end_year, fuels in data:
        for year in range(start_year, end_year): # range is exclusive at end
            for fuel in fuels:
                # Basic sanity checks or exclusions could be added here
                val = f"('{brand}', '{model}', {year}, '{fuel}')"
                values.append(val)

    if values:
        f.write(',\n'.join(values) + ';\n')
    else:
        f.write('-- No data generated;\n')

print(f"Generated {len(values)} rows in {output_file}")
