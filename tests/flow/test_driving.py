import requests
import json
import time
import os
from datetime import datetime

# 설정
BASE_URL = "http://localhost:8080/api/v1"
VEHICLE_ID = "0f9ac11b-8b78-47cd-8b88-3eb535c42e65"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIyOWVlY2M0Ni1mYWU4LTQwYzQtOTIwZC1lNDg0YWVmNzAwZTEiLCJpYXQiOjE3Njg4NDY0NzIsImV4cCI6MTc2ODg1MDA3Mn0.9yCbAH8llpSonzHaGLePy2UVPkZVpwfG3GKZiKHSrtCopi8atnJkikgoyhsrHAZB1Re3rIiJvdQ08chMKMx9iA"

def get_headers():
    # 1. 파일이 있으면 파일 우선
    if os.path.exists("token.json"):
        with open("token.json", "r") as f:
            data = json.load(f)
            return {"Authorization": f"Bearer {data['accessToken']}"}
    
    # 2. 파일 없으면 소스코드 내 변수 사용
    if ACCESS_TOKEN != "YOUR_ACCESS_TOKEN_HERE":
        return {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        
    print("[-] 토큰이 없습니다. token.json을 만들거나 소스코드의 ACCESS_TOKEN 변수를 채워주세요.")
    return None

def start_trip(vehicle_id):
    headers = get_headers()
    if not headers: return None

    print(f"[*] Trip Starting... Vehicle: {vehicle_id}")
    res = requests.post(f"{BASE_URL}/trips/start", json={"vehicleId": vehicle_id}, headers=headers)
    if res.status_code == 200 or res.status_code == 201:
        data = res.json()['data']
        print(f"[+] Trip Started! ID: {data['tripId']}")
        return data['tripId']
    else:
        print(f"[-] Trip Start Failed: {res.text}")
        return None

def send_bulk_logs(vehicle_id):
    import random
    
    headers = get_headers()
    if not headers: return
    
    LOG_COUNT = 500
    print(f"[*] Sending Bulk Logs ({LOG_COUNT} EA / Aggressive Mode)...")
    
    logs = []
    base_time = time.time()
    
    # 초기 속도/RPM
    current_speed = 0.0
    current_rpm = 800.0
    
    for i in range(LOG_COUNT):
        # 짧은 간격 (백엔드 거리 계산 공식 활용)
        ts = datetime.fromtimestamp(base_time + (i * 0.002)).isoformat()
        
        # 난폭 운전 (점수 깎기: 속도 > 140 또는 RPM > 5000)
        if i % 5 == 0: # 5번마다 급발진
            current_speed = random.uniform(145.0, 160.0) # 과속 (점수 감점 트리거)
            current_rpm = random.uniform(5200.0, 6500.0) # 고RPM (점수 감점 트리거)
        else:
            # 평소에도 좀 거칠게
            current_speed = random.uniform(80.0, 130.0)
            current_rpm = random.uniform(2000.0, 4500.0)

        log = {
            "timestamp": ts,
            "vehicleId": vehicle_id,
            "rpm": round(current_rpm, 1),
            "speed": round(current_speed, 1),
            "voltage": round(13.5 + random.uniform(-0.2, 0.2), 1),
            "coolantTemp": round(90.0 + random.uniform(-2, 5), 1),
            "engineLoad": round(45.0 + random.uniform(-10, 10), 1),
            "fuelTrimShort": 2.5,
            "fuelTrimLong": 1.0
        }
        logs.append(log)

    chunk_size = 100
    for i in range(0, len(logs), chunk_size):
        chunk = logs[i:i + chunk_size]
        res = requests.post(f"{BASE_URL}/telemetry/batch", json=chunk, headers=headers)
        if res.status_code == 200:
             print(f"   [+] Batch {i//chunk_size + 1} sent ({len(chunk)} logs)")
        else:
             print(f"   [-] Batch failed: {res.text}")

def end_trip(trip_id):
    headers = get_headers()
    if not headers: return

    print(f"[*] Ending Trip: {trip_id}")
    res = requests.post(f"{BASE_URL}/trips/end", json={"tripId": trip_id}, headers=headers)
    if res.status_code == 200:
        data = res.json()['data']
        print("="*30)
        print("[+] Trip Ended Successfully!")
        print(f"    - Trip ID: {data.get('tripId')}")
        print(f"    - Distance: {data.get('distance')} km")
        print(f"    - Avg Speed: {data.get('averageSpeed')} km/h")
        print(f"    - Score: {data.get('driveScore')}")
        print("="*30)
    else:
        print(f"[-] Trip End Failed: {res.text}")

if __name__ == "__main__":
    if VEHICLE_ID == "YOUR_VEHICLE_UUID_HERE":
        print("❌ 스크립트 파일(test_driving.py)을 열어서 VEHICLE_ID를 먼저 설정해주세요!")
    else:
        tid = start_trip(VEHICLE_ID)
        if tid:
            send_bulk_logs(VEHICLE_ID)
            # time.sleep(1) 
            end_trip(tid)
