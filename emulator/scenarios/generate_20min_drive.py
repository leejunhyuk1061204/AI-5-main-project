"""
20분 주행 시나리오 CSV 생성 (진짜 운전처럼 고정 패턴, 운전점수 감점 최소화)

타임라인:
  0~1분   : 시동 끔 (rpm=0, speed=0)
  1~3분   : 시동 켬 + 대기 (공회전)
  3~18분  : 주행 (부드러운 가속-정속-감속, 급가속/급감속 없음)
  18~19분 : 시동 켬 + 대기 (공회전)
  19~20분 : 시동 끔

운전점수: 공회전 60초마다 -1점만 적용되므로 3분 공회전 = -3점 → 97점 예상.
급가속/급감속(초당 ±10km/h) 미발생, 과속·고RPM·풀스로틀·과부하 없음.
"""

import csv
import os
import math

# replay interval 0.5초 → 1초당 2행
SECS_PER_ROW = 0.5
ROWS_PER_MIN = int(60 / SECS_PER_ROW)  # 120


def _idle_row(seed_idx, coolant=88.0):
    """공회전 1행: RPM 800~950, speed 0, throttle/load 낮음 (미세 변동만)."""
    t = seed_idx % 37
    rpm = 820 + (t * 3) % 130
    return [
        rpm,
        0,
        round(coolant + (t % 5) * 0.3, 1),
        15 + (t % 6),
        round(13.9 + (t % 4) * 0.1, 1),
        28 + (t % 5),
        round(3.5 + (t % 3) * 0.2, 1),
        26 + (t % 4),
        8 + (t % 4),
        (t - 2) % 5 - 2,
        (t - 1) % 5 - 2,
    ]


def _engine_off_row():
    """시동 끔: RPM 0, 속도 0."""
    return [0, 0, 85, 0, 12.5, 30, 0, 35, 0, 0, 0]


def _driving_speed_at_sec(driving_sec):
    """
    주행 구간(0~900초) 내 초당 목표 속도(km/h).
    - 0~60초: 0 → 50 선형 가속 (초당 약 0.83 km/h, 감점 없음)
    - 60~720초: 48~52 크루즈 (작은 변동)
    - 720~900초: 50 → 0 선형 감속 (초당 약 -0.28 km/h)
    """
    if driving_sec < 60:
        return 50.0 * driving_sec / 60.0
    if driving_sec < 720:
        # 크루즈: 50 근처, 약한 사인 변동
        phase = (driving_sec - 60) / 660.0 * 4 * math.pi
        return 50.0 + 2.0 * math.sin(phase)
    if driving_sec <= 900:
        t = (driving_sec - 720) / 180.0  # 0~1
        return 50.0 * (1.0 - t)
    return 0.0


def _driving_row(driving_sec, speed_kmh, row_idx):
    """주행 1행: 속도에 맞춘 RPM/부하/스로틀 (전부 감점 기준 이하)."""
    # RPM: 시내 주행 1500~2800, 5000 미만 유지
    rpm = 1200 + speed_kmh * 28 + (row_idx % 5) * 2
    rpm = min(max(int(rpm), 900), 2800)
    # 냉각수 85~92 (95 미만)
    coolant = 86.0 + (row_idx % 7) * 0.5
    # 부하/스로틀 90 미만 (감점 방지)
    load = min(75.0, 20.0 + speed_kmh * 0.9 + (row_idx % 5))
    throttle = min(65.0, 15.0 + speed_kmh * 0.7 + (row_idx % 4))
    map_kpa = 35 + int(speed_kmh * 0.8) + (row_idx % 3)
    map_kpa = min(map_kpa, 85)
    maf = 5.0 + speed_kmh * 0.25 + (row_idx % 3) * 0.1
    return [
        rpm,
        round(speed_kmh, 1),
        round(coolant, 1),
        round(load, 1),
        round(14.0 + (row_idx % 3) * 0.1, 1),
        map_kpa,
        round(maf, 1),
        28 + (row_idx % 5),
        round(throttle, 1),
        (row_idx - 1) % 5 - 2,
        (row_idx % 5) - 2,
    ]


def generate_20min_drive_csv():
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "scenario_20min_drive.csv")
    headers = [
        "rpm", "speed", "temp", "load", "voltage", "map", "maf",
        "intake_temp", "throttle", "fuel_trim_short", "fuel_trim_long",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)

        # 1. 시동 끔 1분 (0~60초) = 120행
        for _ in range(ROWS_PER_MIN):
            w.writerow(_engine_off_row())

        # 2. 시동 켬 + 대기 2분 (60~180초) = 240행
        for i in range(240):
            w.writerow(_idle_row(i, coolant=52.0 + i * 0.05))

        # 3. 주행 15분 (180~1080초) = 900초 = 1800행
        for i in range(1800):
            driving_sec = (i + 1) * SECS_PER_ROW  # 0.5, 1.0, ... 900.0
            speed = _driving_speed_at_sec(driving_sec)
            w.writerow(_driving_row(driving_sec, speed, i))

        # 4. 시동 켬 + 대기 1분 (1080~1140초) = 120행
        for i in range(120):
            w.writerow(_idle_row(240 + i, coolant=88.0))

        # 5. 시동 끔 1분 (1140~1200초) = 120행
        for _ in range(ROWS_PER_MIN):
            w.writerow(_engine_off_row())

    total_rows = 120 + 240 + 1800 + 120 + 120
    print(f"Generated {path} ({total_rows} rows, 20 min at {SECS_PER_ROW}s interval)")
    print("Phases: 1min OFF, 2min IDLE, 15min DRIVE, 1min IDLE, 1min OFF. Score-friendly (no hard accel/brake).")
    return path


if __name__ == "__main__":
    generate_20min_drive_csv()
