import requests
import json
import time
import os
import sys
import random
from datetime import datetime

# 설정
BASE_URL = "http://localhost:8080/api/v1"
VEHICLE_ID = "9db0e652-a852-4fdb-bda4-a86adeb3778b"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJlNmQ5ODU5MS04ZTRlLTRlMTEtOTI5YS1jZDg3NDk3MDdmYWIiLCJpYXQiOjE3NzAxMDgxMTYsImV4cCI6MTc3MDExMTcxNn0.mOVLrnD-69MA95wvXA_VNtYAHLV7uKdbQdjLYMcYhFzm2IMmAOtHYPvMDh0dVRR03vlGTHYvaJWN2kVak7ItEA"

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
            "fuelTrimLong": 1.0,
            "intakeTemp": round(25.0 + random.uniform(0, 5), 1),
            "map": round(30.0 + random.uniform(5, 70), 1),
            "maf": round(15.0 + random.uniform(2, 40), 1),
            "throttlePos": round(15.0 + random.uniform(0, 80), 1),
            "engineRuntime": 3600
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
        print(f"    - Avg RPM: {data.get('avgRpm')}")
        print(f"    - Avg Engine Load: {data.get('avgEngineLoad')}")
        print(f"    - Overheat Duration: {data.get('overheatDurationSec')} sec")
        print(f"    - Hard Accel Count: {data.get('hardAccelCount')}")
        print(f"    - Score: {data.get('driveScore')}")
        print("="*30)
    else:
        print(f"[-] Trip End Failed: {res.text}")

import argparse

def main():
    parser = argparse.ArgumentParser(description="Driving Data Simulation Test")
    parser.add_argument("--duration", type=float, default=5, help="주행 시간 (분)")
    parser.add_argument("--interval", type=int, default=1, help="데이터 생성 간격 (초)")
    parser.add_argument("--batch", type=int, default=60, help="배치 전송 단위 (초)")
    
    args = parser.parse_args()
    
    print(f"[*] Starting simulation for {args.duration} minutes...")
    print(f"[*] Config: Interval={args.interval}s, Batch={args.batch}s")
    
    tid = start_trip(VEHICLE_ID)
    if tid:
        try:
            # send_bulk_logs 내부 로직을 args에 맞춰 수정하고 싶으나, 
            # 일단 기존 함수를 호출 (필요시 send_bulk_logs 시그니처 수정)
            send_bulk_logs(VEHICLE_ID, args.duration)
            end_trip(tid)
        except KeyboardInterrupt:
            print("\n[!] 테스트가 중단되었습니다. 주행을 종료합니다.")
            end_trip(tid)
        except Exception as e:
            print(f"\n[!] 오류 발생: {e}")
            end_trip(tid)

if __name__ == "__main__":
    main()
