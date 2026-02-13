import uuid
import time
import requests
import random
from datetime import datetime, timedelta

# 설정
BASE_URL = "http://localhost:8080/api/v1"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI5ZmM0OTMyYi04ZjI2LTRkOGItOGZjZC02MWNkOGNjZDc4OTgiLCJpYXQiOjE3NzA5NjQ5MjksImV4cCI6MTc3MDk2ODUyOX0.7nlkF6Z2WbMz8sP0mE956dz7K5bENmlsGdDO12fJdxk8oAMjNSxUBL0WYJ67SLIhpJHX6680ByWuspwPCy4jnA"
VEHICLE_ID = "3437b1fd-ba3d-4d0e-ab72-cfdd9c586e75"

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

def send_bulk_logs(vehicle_id, target_duration_min, start_time_base, target_s_min, target_s_max):
    headers = get_headers()
    log_count = int(target_duration_min * 60)
    target_mid = (target_s_min + target_s_max) / 2.0
    print(f"[*] Sending Bulk Logs ({log_count} EA, {target_duration_min}min / Avg {target_mid:.0f}km/h, Score 80~90)...")
    
    logs = []
    base_time = start_time_base + timedelta(milliseconds=10)
    current_speed = 0.0
    # 급가속 감점 방지: 초당 10km/h 미만으로 가속 (백엔드 HARD_ACCEL_THRESHOLD)
    max_accel_per_sec = 8.0

    for i in range(log_count):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        
        if current_speed < target_s_min:
            current_speed += random.uniform(2.0, min(max_accel_per_sec, target_s_min - current_speed))
        else:
            current_speed = current_speed + random.uniform(
                max(target_s_min - current_speed, -1.5),
                min(target_s_max - current_speed, 1.5)
            )
            current_speed = max(target_s_min, min(target_s_max, current_speed))
        
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
    duration_min = 10.0
    speed_min, speed_max = 80.0, 90.0
    print(f"[*] {duration_min:.0f}분 주행 시뮬레이션 (평균 {speed_min:.0f}~{speed_max:.0f} km/h, 목표 점수 80~90)")
    vid = VEHICLE_ID

    start_time = datetime.now()
    tid = start_trip(vid)
    if not tid:
        return
    time.sleep(0.5)
    send_bulk_logs(vid, duration_min, start_time, speed_min, speed_max)
    time.sleep(1.0)
    end_trip(tid)
    print(f"\n[+] {duration_min:.0f}분 주행 시뮬레이션 완료.")

if __name__ == "__main__":
    main()
