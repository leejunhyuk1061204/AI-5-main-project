import requests
import json
import time
import os
from datetime import datetime

# 설정
BASE_URL = "http://localhost:8080/api/v1"
VEHICLE_ID = "6e67c1d5-bab2-426d-954a-0322d6f547f2"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI2ZjcxOThmZi05NTJjLTQzOGQtYmIxMi0xOTQ0YmJiYjc3OTciLCJpYXQiOjE3Njk0OTU4MzEsImV4cCI6MTc2OTQ5OTQzMX0.C0FZyZXpzttr9zGFXa6It2euyiOh3kmubgQuQbG6Uwvz36Y_Qf4vi377Q_kIyIcJI0JZ_JFXOWvbROy13-t-hw"

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
    
    LOG_COUNT = 3500
    print(f"[*] Sending Bulk Logs ({LOG_COUNT} EA / Aggressive Mode)...")
    
    logs = []
    # [Active] 현재 시간 기준으로 +0.01초씩 증가 (고속 데이터 전송 시뮬레이션)
    base_time = time.time()
    
    # 초기 속도/RPM
    current_speed = 0.0
    current_rpm = 800.0
    
    for i in range(LOG_COUNT):
        # 0.01초 간격 타임스탬프 (Backend counts 1 log = 1 sec driving distance)
        ts = datetime.fromtimestamp(base_time + (i * 0.01)).isoformat()
        
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
        
        # Fast processing: minimal sleep
        time.sleep(0.5)

    # Ensure we wait until the last timestamp has passed in wall clock time
    # Total duration = 3500 * 0.01 = 35 seconds
    elapsed = time.time() - base_time
    remaining = 36 - elapsed
    if remaining > 0:
        print(f"   ...Waiting {remaining:.1f}s for timestamps to catch up...")
        time.sleep(remaining)

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
