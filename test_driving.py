import requests
import json
import time
import os
from datetime import datetime

# 설정
BASE_URL = "http://localhost:8080/api/v1"
VEHICLE_ID = "4f3038d7-84b5-4048-b9e4-6276323f834a" # <- 여기에 본인 차량 ID 입력하세요
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI5NmUzNTQyYy0zNzY5LTQwZmEtYmJiYS1hYjA1OWExNmJlYTUiLCJpYXQiOjE3Njg4MTI2MTUsImV4cCI6MTc2ODgxNjIxNX0.umx-JCBzCnL09Hz0_wCWXocuYtJyz884Y8atGUhbZhErLNVmK3LXRRQDE8AlASmM6GXwTseSbOB5kIEDKmW_hA" # <- 여기에 토큰 붙여넣으세요 (Bearer 없이 토큰값만)

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
    
    LOG_COUNT = 300 # 300개 (5분 분량)
    print(f"[*] Sending Bulk Logs ({LOG_COUNT} EA / 5 mins driving)...")
    
    logs = []
    # 핵심 수정: 현재 시간 기준 + 밀리초 오프셋으로 고유 타임스탬프 생성
    # Trip window 안에 들어가면서 PK 중복도 피함
    base_time = time.time()
    
    # 초기 속도/RPM
    current_speed = 0.0
    current_rpm = 800.0
    
    for i in range(LOG_COUNT):
        # 각 로그마다 0.001초(1ms) 씩 증가하여 고유하게 만듦
        ts = datetime.fromtimestamp(base_time + (i * 0.001)).isoformat()
        
        # 간단한 주행 시뮬레이션 (가속 -> 정속 -> 감속)
        if i < 30: # 초반 30초 가속
            current_speed = min(100.0, current_speed + 3.5)
            current_rpm = min(3000.0, current_rpm + 80)
        elif i > LOG_COUNT - 30: # 막판 30초 감속
            current_speed = max(0.0, current_speed - 3.5)
            current_rpm = max(800.0, current_rpm - 80)
        else: # 정속 주행 (약간의 변동)
            current_speed += random.uniform(-2.0, 2.0)
            current_rpm += random.uniform(-50, 50)
            
            # 범위 제한
            current_speed = max(0, min(160, current_speed))
            current_rpm = max(800, min(6000, current_rpm))

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
