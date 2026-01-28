import requests
import json
import time
import os
import sys
import random
from datetime import datetime

# 설정
BASE_URL = "http://localhost:8080/api/v1"
VEHICLE_ID = "32cbfa4d-ed68-44fd-b13e-36fe357bd74f"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIyZmQyMDE4MS1mYmE1LTQwYzYtOGFlNi1jMjg5N2YwYTE0ZjciLCJpYXQiOjE3Njk1ODkyMzQsImV4cCI6MTc2OTU5MjgzNH0.sFVtVplcBLleUJYPRoG2qoazSZ6thu_Ab_WLVts0fIR6_n7qqD8GkaHfZmK0aTdZuOnJy7v9kTP6oNDJr8_okg"

def get_headers():
    if os.path.exists("token.json"):
        with open("token.json", "r") as f:
            data = json.load(f)
            return {"Authorization": f"Bearer {data['accessToken']}"}
    
    if ACCESS_TOKEN:
        return {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        
    print("[-] 토큰이 없습니다.")
    return None

def start_trip(vehicle_id):
    headers = get_headers()
    if not headers: return None

    print(f"[*] Trip Starting... Vehicle: {vehicle_id}")
    res = requests.post(f"{BASE_URL}/trips/start", json={"vehicleId": vehicle_id}, headers=headers)
    if res.status_code in [200, 201]:
        data = res.json()['data']
        print(f"[+] Trip Started! ID: {data['tripId']}")
        return data['tripId']
    else:
        print(f"[-] Trip Start Failed (Status: {res.status_code}): {res.text}")
        return None

def send_bulk_logs(vehicle_id, target_km):
    headers = get_headers()
    if not headers: return
    
    # 1 log = 약 1초 주행 거리 (평균 100km/h 가정 시 1km = 36 logs)
    # 3000km = 약 108,000 logs
    log_count = int(target_km * 34) # 약간의 오차를 위해 34 사용
    # 자연스러움을 위해 목표값에 +- 5% 랜덤 추가
    log_count = int(log_count * random.uniform(0.95, 1.05))
    
    print(f"[*] Sending Bulk Logs ({log_count} EA / Targeting ~{target_km}km)...")
    
    logs = []
    base_time = time.time()
    
    current_speed = 0.0
    current_rpm = 800.0
    
    for i in range(log_count):
        # 타임스탬프 (Backend counts 1 log = 1 sec driving distance)
        ts = datetime.fromtimestamp(base_time + i).isoformat()
        
        # 자연스러운 주행 시뮬레이션 (가속/감속 트렌드)
        if current_speed < 100: # 가속 구간
            current_speed += random.uniform(0.5, 2.0)
            current_rpm = current_speed * 30 + random.uniform(500, 1000)
        elif current_speed > 130: # 과속 구간 제어
            current_speed -= random.uniform(0.1, 1.0)
            current_rpm = current_speed * 25 + random.uniform(200, 500)
        else: # 정속 주행 구간
            current_speed += random.uniform(-1.5, 1.5)
            current_rpm = current_speed * 25 + random.uniform(-100, 300)

        # 간헐적 과속/고RPM (이벤트 발생)
        if random.random() < 0.01: # 1% 확률로 급가속
            current_speed = random.uniform(145.0, 160.0)
            current_rpm = random.uniform(5500.0, 6500.0)

        log = {
            "timestamp": ts,
            "vehicleId": vehicle_id,
            "rpm": round(max(800, current_rpm), 1),
            "speed": round(max(0, current_speed), 1),
            "voltage": round(13.5 + random.uniform(-0.2, 0.2), 1),
            "coolantTemp": round(90.0 + random.uniform(-2, 5), 1),
            "engineLoad": round(45.0 + random.uniform(-10, 10), 1),
            "fuelTrimShort": 2.5,
            "fuelTrimLong": 1.0
        }
        logs.append(log)

    chunk_size = 200 # 전송 속도 향상을 위해 청크 크기 확대
    for i in range(0, len(logs), chunk_size):
        chunk = logs[i:i + chunk_size]
        res = requests.post(f"{BASE_URL}/telemetry/batch", json=chunk, headers=headers)
        if res.status_code == 200:
             if (i // chunk_size) % 50 == 0: # 로그 너무 많이 찍히지 않게 조절
                print(f"   [+] Sent {i}/{log_count} logs...")
        else:
             print(f"   [-] Batch failed: {res.text}")
        
        # 고속 전송을 위해 sleep 최소화 (장거리인 경우 더 빠르게)
        time.sleep(0.01 if target_km > 500 else 0.05)

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
    target_distance = 70 # 기본값
    if len(sys.argv) > 1:
        target_distance = float(sys.argv[1])
    
    tid = start_trip(VEHICLE_ID)
    if tid:
        try:
            send_bulk_logs(VEHICLE_ID, target_distance)
            end_trip(tid)
        except KeyboardInterrupt:
            print("\n[!] 테스트가 중단되었습니다. 주행을 종료합니다.")
            end_trip(tid)
