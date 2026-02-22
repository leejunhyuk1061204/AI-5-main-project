import requests
import random
import time
from datetime import datetime, timedelta

# User provided config
BASE_URL = "http://localhost:8080/api/v1"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIxOWVjYTg1Yy1iMWI3LTQyNTEtOThhNi0yYWJlYWRiNWZmNDEiLCJpYXQiOjE3NzE0ODAxMjksImV4cCI6MTc3MTQ4MzcyOX0.pn-HxT4zvTlwHDRuInU0TwslqH4UXkM1VxO4mPthkLuQJFYNaldKfwrBJtFXTpC6vTmLgXIqOF_sVpkcNOiC9A"
VEHICLE_ID = "75072020-0bbe-4eb2-a583-00fec842a8c2"

def get_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

def start_trip(vehicle_id):
    headers = get_headers()
    print(f"[*] Trip Starting... Vehicle: {vehicle_id}")
    res = requests.post(f"{BASE_URL}/trips/start", json={"vehicleId": vehicle_id}, headers=headers)
    if res.status_code == 200:
        trip_id = res.json()['data']['tripId']
        print(f"[+] Trip Started! ID: {trip_id}")
        return trip_id
    else:
        print(f"[-] Trip Start Failed: {res.text}")
        return None

import os
import subprocess

def clear_vehicle_data(vehicle_id):
    print(f"[*] Clearing data for vehicle {vehicle_id}...")
    env = os.environ.copy()
    env['PGPASSWORD'] = 'postgres'
    cmds = [
        f"DELETE FROM obd_logs WHERE vehicles_id = '{vehicle_id}';",
        f"DELETE FROM trip_summaries WHERE vehicles_id = '{vehicle_id}';"
    ]
    for c in cmds:
        try:
            subprocess.run(
                ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'car_sentry', '-c', c],
                env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            print(f"[-] Cleanup failed (non-fatal): {e.stderr.decode()}")

def fix_trip_end_time(trip_id, end_time_iso):
    print(f"[*] Fixing end time for trip {trip_id} to {end_time_iso}...")
    query = f"UPDATE trip_summaries SET end_time = '{end_time_iso}' WHERE trip_id = '{trip_id}';"
    env = os.environ.copy()
    env['PGPASSWORD'] = 'postgres'
    try:
        subprocess.run(
            ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'car_sentry', '-c', query],
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        print(f"[-] Failed to fix end time: {e.stderr.decode()}")

def force_update_trip_stats(trip_id, distance, score):
    print(f"[*] Forcing stats for trip {trip_id}: Dist={distance}km, Score={score}...")
    query = f"UPDATE trip_summaries SET distance = {distance}, drive_score = {score} WHERE trip_id = '{trip_id}';"
    env = os.environ.copy()
    env['PGPASSWORD'] = 'postgres'
    try:
        subprocess.run(
            ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'car_sentry', '-c', query],
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        print(f"[-] Failed to force stats: {e.stderr.decode()}")

def backdate_trip(trip_id, start_time_iso):
    print(f"[*] Backdating trip {trip_id} to {start_time_iso}...")
    # Update start_time in DB explicitly
    query = f"UPDATE trip_summaries SET start_time = '{start_time_iso}' WHERE trip_id = '{trip_id}';"
    env = os.environ.copy()
    env['PGPASSWORD'] = 'postgres'
    
    try:
        subprocess.run(
            ['psql', '-h', 'localhost', '-U', 'postgres', '-d', 'car_sentry', '-c', query],
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        print(f"[-] Failed to backdate trip: {e.stderr.decode()}")

def send_bulk_logs(trip_id, vehicle_id, start_time, duration_min, event_count):
    headers = get_headers()
    log_count = int(duration_min * 60)
    print(f"[*] Sending Bulk Logs ({log_count} EA)... Target Bad Events: {event_count}")
    
    # Pick specific times for events
    event_indices = set(random.sample(range(10, log_count - 10), min(event_count, log_count - 20))) if event_count > 0 else set()
    
    logs = []
    current_speed = 0.0
    
    target_speed = random.choice([150, 180, 200, 250, 300]) 

    for i in range(log_count):
        ts = (start_time + timedelta(seconds=i)).isoformat()
        
        if i in event_indices:
            # Event!
            if random.random() < 0.5:
                # Rapid Accel
                current_speed += random.uniform(20, 30)
            else:
                # Hard Brake
                current_speed -= random.uniform(20, 30)
        else:
            # Normal Driving - matching original script logic
            if current_speed < target_speed:
                current_speed += random.uniform(2.0, 5.0)
            else:
                current_speed = target_speed + random.uniform(-2.0, 2.0)
        
        # Ensure physics constraints
        current_speed = max(0, min(current_speed, 300)) 
        
        current_rpm = current_speed * 25 + 1000 + random.uniform(-20, 20)
        if current_speed > 100: current_rpm += 500 # Higher RPM for high speed

        log = {
            "timestamp": ts,
            "vehicleId": vehicle_id,
            "rpm": round(max(800, current_rpm), 1),
            "speed": round(current_speed, 1),
            "voltage": 14.1 + random.uniform(-0.1, 0.1),
            "coolantTemp": 90.0 + random.uniform(-2, 2),
            "engineLoad": 25.0 + random.uniform(-5, 5),
            "intakeTemp": 28.0,
            "engineRuntime": 3600 + i,
            "tripId": trip_id 
        }
        logs.append(log)

    # Send in chunks
    chunk_size = 100 
    import uuid
    for i in range(0, len(logs), chunk_size):
        chunk = logs[i:i + chunk_size]
        
        payload = {
            "batchId": str(uuid.uuid4()),
            "vehicleId": vehicle_id,
            "logs": chunk
        }
        
        res = requests.post(f"{BASE_URL}/telemetry/batch", json=payload, headers=headers)
        if res.status_code != 200:
                print(f"[-] Log Batch Failed: {res.text}")

def end_trip(trip_id):
    headers = get_headers()
    print(f"[*] Ending Trip: {trip_id}")
    res = requests.post(f"{BASE_URL}/trips/end", json={"tripId": trip_id}, headers=headers)
    if res.status_code == 200:
        d = res.json()['data']
        print(f"[+] Trip Ended. Dist: {d.get('distance')}km, Score: {d.get('driveScore')}")
    else:
        print(f"[-] Trip End Failed: {res.text}")

def main():
    clear_vehicle_data(VEHICLE_ID)
    print(f"[*] Starting 10 iterations with RANDOM event counts for Vehicle {VEHICLE_ID}")
    
    total_iterations = 200
    base_duration_min = 10 

    for i in range(1, total_iterations + 1):
        # Target Score ~70 means ~6 bad events (6 * 5 = 30 deduction).
        # Randomize between 2 and 8 to get scores roughly in 60-90 range.
        event_count = random.randint(2, 6) # Reduced slightly to avoid 0s if penalties stack
        
        # Randomize date within last 7 days
        days_ago = random.randint(0, 6)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        
        log_start_time = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
        
        print(f"\n[{i}/{total_iterations}] Starting Iteration with {event_count} bad events (Time: {log_start_time.strftime('%Y-%m-%d %H:%M')})...")
        
        trip_id = start_trip(VEHICLE_ID)
        if trip_id:
            # Backdate the trip in DB using the ISO string
            backdate_trip(trip_id, log_start_time.isoformat())
            
            send_bulk_logs(trip_id, VEHICLE_ID, log_start_time, base_duration_min, event_count)
            try:
                end_trip(trip_id)
            except Exception as e:
                print(f"[-] Trip End Exception: {e}")
            
            time.sleep(2) # Wait for backend async processing
            
            # Fix end time
            log_end_time = log_start_time + timedelta(minutes=base_duration_min)
            fix_trip_end_time(trip_id, log_end_time.isoformat())
            
            # Force reasonable stats
            fake_dist = round(random.uniform(5.0, 20.0), 1)
            fake_score = random.randint(65, 95)
            force_update_trip_stats(trip_id, fake_dist, fake_score)
            
            print(f"[+] Iteration {i} Complete.")
            time.sleep(1) 
        else:
            print(f"[-] Skipping iteration {i} due to start failure.")

if __name__ == "__main__":
    main()
