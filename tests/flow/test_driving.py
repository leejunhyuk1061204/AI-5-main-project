import uuid
import time
import requests
import random
from datetime import datetime, timedelta

# 설정
BASE_URL = "http://localhost:8080/api/v1"
ACCESS_TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJlNjE2MjYzNC1kMTI3LTQzYmQtODRjYS03NTcwYWRjYmMzOTgiLCJpYXQiOjE3NzExNDA1MDIsImV4cCI6MTc3MTE0NDEwMn0.vjwl83lELUY6pNIK28tYJm4-6wxDXAAFNsHM_4awop7Hw380_tawhVCioUGgzSzzZrx83p-ocBPZSoJ01jvcmg"
VEHICLE_ID = "dbdae6b8-8557-456a-95f1-921f48f836df"

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
    """
    주행점수 ~90점 목표: 급가속 1회(-5), 급감속 1회(-5) = 100 - 10.
    백엔드 HARD_ACCEL/HARD_BRAKE_THRESHOLD = 10 km/h/s 이므로 초당 ±12 km/h 이벤트 삽입.
    """
    headers = get_headers()
    log_count = int(target_duration_min * 60)
    target_mid = (target_s_min + target_s_max) / 2.0
    print(f"[*] Sending Bulk Logs ({log_count} EA, {target_duration_min}min / Avg {target_mid:.0f}km/h, 목표 점수 ~90)...")
    
    logs = []
    base_time = start_time_base + timedelta(milliseconds=10)
    current_speed = 0.0
    max_accel_per_sec = 8.0
    # 급감속 1회(초 120), 급가속 1회(초 300) → 각 -5점
    hard_brake_sec, hard_accel_sec = 120, 300

    for i in range(log_count):
        ts = (base_time + timedelta(seconds=i)).isoformat()
        
        if i == hard_brake_sec:
            current_speed = max(0.0, current_speed - 12.0)
        elif i == hard_accel_sec:
            current_speed = min(target_s_max, current_speed + 12.0)
        elif current_speed < target_s_min:
            current_speed += random.uniform(2.0, min(max_accel_per_sec, target_s_min - current_speed))
        else:
            current_speed = current_speed + random.uniform(
                max(target_s_min - current_speed, -1.5),
                min(target_s_max - current_speed, 1.5)
            )
            current_speed = max(target_s_min, min(target_s_max, current_speed))
        
        current_rpm = current_speed * 18 + 1200 + random.uniform(-10, 10)
        # MAF: 흡기량 (속도·부하와 연동). 에어필터/스파크플러그 등 공식에 사용
        maf = 10.0 + (current_speed / 10.0) + (current_speed * 0.15) + random.uniform(0, 2)
        # throttle/load: 주행점수 감점(>90) 방지로 상한 85 근처 유지
        throttle = min(85.0, 25.0 + (current_speed / 2.0) + random.uniform(-5, 10))
        engine_load = min(85.0, 15.0 + (current_speed / 5.0) + random.uniform(0, 10))

        log = {
            "timestamp": ts,
            "vehicleId": vehicle_id,
            "rpm": round(max(800, current_rpm), 1),
            "speed": round(max(0, current_speed), 1),
            "voltage": 14.2,
            "coolantTemp": 90.0,
            "engineLoad": round(min(95.0, engine_load), 1),
            "intakeTemp": 25.0,
            "engineRuntime": 3600,
            "maf": round(maf, 2),
            "throttle": round(throttle, 1),
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
    speed_min, speed_max = 50.0, 90.0
    print(f"[*] {duration_min:.0f}분 주행 시뮬레이션 (시내주행 {speed_min:.0f}~{speed_max:.0f} km/h, 목표 점수 90 전후)")
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
