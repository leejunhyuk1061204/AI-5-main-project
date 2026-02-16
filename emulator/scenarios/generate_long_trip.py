
import csv
import random

def generate_trip():
    import os
    # 스크립트가 있는 폴더(scenarios)에 test_trip.csv 생성
    filename = os.path.join(os.path.dirname(__file__), 'test_trip.csv')
    headers = ['rpm', 'speed', 'temp', 'load', 'voltage', 'map', 'maf', 'intake_temp', 'throttle', 'fuel_trim_short', 'fuel_trim_long']
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        # 1. Ignition On / Idle (30 sec)
        print("Generating Idle phase...")
        for _ in range(60): # 0.5s interval * 60 = 30s
            writer.writerow([
                random.randint(650, 750), # RPM (Adjusted to realistic idle)
                0,                        # Speed
                random.randint(40, 60),   # Temp
                random.randint(15, 20),   # Load
                f"{random.uniform(13.8, 14.2):.1f}", # Voltage
                random.randint(95, 105),  # MAP
                f"{random.uniform(4.0, 6.0):.1f}", # MAF
                random.randint(20, 25),    # Intake Temp
                random.randint(10, 12),    # Throttle
                random.randint(-2, 2),     # Fuel Trim Short
                random.randint(-2, 2)      # Fuel Trim Long
            ])

        # 2. Driving (4 mins = 240 sec)
        print("Generating Driving phase...")
        for i in range(480): # 0.5s * 480 = 240s
            speed = random.randint(20, 100)
            rpm = random.randint(1500, 3000)
            load = random.randint(30, 70)
            map_val = random.randint(110, 150)
            maf = random.uniform(15.0, 40.0)
            
            writer.writerow([
                rpm,
                speed,
                random.randint(80, 95),   # Temp
                load,
                f"{random.uniform(13.8, 14.4):.1f}",
                map_val,
                f"{maf:.1f}",
                random.randint(30, 45),
                random.randint(20, 50),    # Throttle
                random.randint(-5, 5),     # Fuel Trim Short
                random.randint(-5, 5)      # Fuel Trim Long
            ])

        # 2.5 Deceleration & Cooldown (1 min 10 sec total)
        print("Generating Deceleration & Cooldown phase...")
        
        # Slow down (10 sec)
        current_speed = 60
        current_rpm = 2000
        for i in range(20):
            current_speed = max(0, current_speed - 3)
            current_rpm = max(700, current_rpm - 65)
            writer.writerow([
                int(current_rpm),
                int(current_speed),
                88, 20, "14.0", 100, "6.0", 35, 10, 0, 0
            ])

        # Idle Cooldown (1 min) - RPM 650~700
        for _ in range(120):
            writer.writerow([
                random.randint(650, 700), # RPM 
                0,                        # Speed
                random.randint(85, 92),   # Temp (Hot)
                random.randint(15, 18),   # Load
                f"{random.uniform(13.8, 14.1):.1f}",
                random.randint(95, 100),
                f"{random.uniform(3.5, 4.5):.1f}", 
                random.randint(35, 45),
                random.randint(10, 11),
                random.randint(-1, 1),
                random.randint(-1, 1)
            ])

        # 3. Trip End / Ignition Off (30 sec)
        print("Generating Stop phase...")
        for _ in range(60):
            writer.writerow([
                0, 0, 85, 0, 12.5, 100, 0, 40, 0, 0, 0
            ])
            
    print(f"Generated {filename} with ~5 minutes of data.")

if __name__ == "__main__":
    generate_trip()
