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

def send_bulk_logs(vehicle_id, target_duration_min):
    headers = get_headers()
    if not headers: return
    
    # 1 log = 1 sec
    log_count = int(target_duration_min * 60)
    
    print(f"[*] Sending Bulk Logs ({log_count} EA / Duration ~{target_duration_min}min)...")
    
    logs = []
    base_time = time.time()
    # 과거 시간부터 시작해서 현재에 끝나도록 (Backend가 미래 데이터를 거부할 수 있으므로) -> 아니면 그냥 현재부터 미래로? 
    # 보통 DB 저장시 문제 없으므로 현재 시간(base_time)부터 +i 초로 생성
    
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
             if (i // chunk_size) % 10 == 0: 
                print(f"   [+] Sent {min(i+chunk_size, log_count)}/{log_count} logs...")
        else:
             print(f"   [-] Batch failed: {res.text}")
        
        # 고속 전송을 위해 sleep 최소화
        time.sleep(0.01)

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
    target_duration = 17 # 기본값 17분 (1020초)
    if len(sys.argv) > 1:
        target_duration = float(sys.argv[1])
    
    tid = start_trip(VEHICLE_ID)
    if tid:
        try:
            send_bulk_logs(VEHICLE_ID, target_duration)
            end_trip(tid)
        except KeyboardInterrupt:
            print("\n[!] 테스트가 중단되었습니다. 주행을 종료합니다.")
            end_trip(tid)
