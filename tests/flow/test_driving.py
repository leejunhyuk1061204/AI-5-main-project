import uuid
import time
import requests
import random
from datetime import datetime, timedelta

# 설정
BASE_URL = "http://localhost:8080/api/v1"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiIzZGI0NjVjMy1lNThhLTQzYWQtOTUxNy02MTRmNDhjOGVmZjMiLCJpYXQiOjE3NzA2MTI0MDksImV4cCI6MTc3MDYxNjAwOX0.L5alysYSEYAwo-rgiX2MR7vlFLndNbTxVaMsYAe6AKl4dgsGyY-dCFYbeT8MAbh9QwQvp4OVEq8ZTIhy73HecA"
VEHICLE_ID = "690713b3-34ee-45c8-adfe-73af1ad5d798"

def get_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

def create_simulation_vehicle():
    """시뮬레이션 전용 차량을 등록하고 ID를 반환합니다."""
    headers = get_headers()
    # 이미 존재하는지 확인하기보다 매번 새로 만드는 것이 깔끔함 (테스트용)
    payload = {
        "manufacturerKo": "시뮬레이션",
        "modelNameKo": "테스트카_" + str(random.randint(1000, 9999)),
        "modelYear": 2024,
        "fuelType": "GASOLINE",
        "totalMileage": 0.0,
        "nickname": "SIM_VEHICLE"
    }
    print("[*] Creating Fresh Simulation Vehicle...")
    res = requests.post(f"{BASE_URL}/vehicles", json=payload, headers=headers)
    if res.status_code == 201:
        data = res.json()['data']
        vid = data['vehicleId']
        print(f"[+] Simulation Vehicle Created: {vid}")
        return vid
    else:
        print(f"[-] Vehicle Creation Failed: {res.text}")
        return None

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

def send_bulk_logs(vehicle_id, target_duration_min, start_time_base, target_s):
    headers = get_headers()
    # 1초당 1건, 실제 주행 시간 구간에 맞춤 (LSTM/이상감지가 시간 구간 사용)
    log_count = int(target_duration_min * 60)
    print(f"[*] Sending Bulk Logs ({log_count} EA, {target_duration_min}min span / Target {target_s}km/h)...")
    
    logs = []
    base_time = start_time_base + timedelta(milliseconds=10)
    current_speed = 0.0

    for i in range(log_count):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        
        if current_speed < target_s:
            current_speed += random.uniform(2.0, 5.0)
        else:
            current_speed = target_s + random.uniform(-0.1, 0.1)
        
        current_rpm = current_speed * 18 + 1200 + random.uniform(-10, 10)

        log = {
            "timestamp": ts,
            "vehicleId": vehicle_id,
            "rpm": round(max(800, current_rpm), 1),
            "speed": round(max(0, current_speed), 1),
            "voltage": 14.2,
            "coolantTemp": 90.0,
            "engineLoad": 20.0,
            "intakeTemp": 25.0,
            "engineRuntime": 3600
        }
        logs.append(log)

    # API 스펙: { "vehicleId", "batchId", "logs" } (배열만 보내면 저장 안 됨)
    chunk_size = 500
    for i in range(0, len(logs), chunk_size):
        chunk = logs[i:i + chunk_size]
        batch_id = f"driving-{start_time_base.strftime('%Y%m%d%H%M%S')}-{i // chunk_size}"
        payload = {"vehicleId": vehicle_id, "batchId": batch_id, "logs": chunk}
        r = requests.post(f"{BASE_URL}/telemetry/batch", json=payload, headers=headers)
        if r.status_code != 200:
            print(f"[-] Batch chunk {i // chunk_size} failed: {r.status_code} {r.text[:200]}")

def end_trip(trip_id):
    headers = get_headers()
    print(f"[*] Ending Trip: {trip_id}")
    res = requests.post(f"{BASE_URL}/trips/end", json={"tripId": trip_id}, headers=headers)
    if res.status_code == 200:
        d = res.json()['data']
        print("="*35)
        print(f"[+] Trip ID: {d.get('tripId')}")
        print(f"    - Avg Speed: {d.get('averageSpeed'):.2f} km/h")
        print(f"    - Distance: {d.get('distance'):.2f} km")
        print(f"    - Score: {d.get('driveScore')}")
        print("="*35)

def main():
    print("[*] 20분 주행 시뮬레이션 (단일 트립)")
    vid = VEHICLE_ID
    target_speed = 80.0

    start_time = datetime.now()
    tid = start_trip(vid)
    if not tid:
        return
    time.sleep(0.5)
    send_bulk_logs(vid, 20.0, start_time, target_speed)
    time.sleep(1.0)
    end_trip(tid)
    print("\n[+] 20분 주행 시뮬레이션 완료.")

if __name__ == "__main__":
    main()
