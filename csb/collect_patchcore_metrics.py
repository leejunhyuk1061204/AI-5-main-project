import os
import json
from pathlib import Path

def collect_metrics():
    results_root = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\patchcore")
    parts = [
        "ABS_Unit", "Air_Filter_Cover", "Battery", "Brake_Fluid", 
        "Engine_Cover", "Engine_Oil_Fill_Cap", "Radiator", "Windshield_Wiper_Fluid"
    ]
    
    summary = {}
    
    for part in parts:
        part_dir = results_root / part / "Patchcore" / part
        # Try to find any metrics file or log file
        # Check if we can find any csv in the directory
        csv_files = list(part_dir.glob("**/*.csv"))
        if csv_files:
            summary[part] = f"Found CSV: {csv_files[0]}"
            # Try to read the last line of the CSV
            try:
                with open(csv_files[0], 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        summary[part] = lines[-1].strip()
            except:
                pass
        else:
            summary[part] = "No CSV found"
            
    # Print what we found
    for part, data in summary.items():
        print(f"{part}: {data}")

if __name__ == "__main__":
    collect_metrics()
