"""
10분 주행 시나리오 CSV 생성 (1+2+5+1+1, 운전점수 감점 최소화)

타임라인:
  0~1분   : 시동 끔 (rpm=0, speed=0)
  1~3분   : 시동 켬 + 대기 (공회전)
  3~8분   : 주행 5분 (시내→신호 정지→고속도로 80~90, 변동 포함)
  8~9분   : 시동 켬 + 대기 (공회전)
  9~10분  : 시동 끔

주행 5분: 시내 가속~정속~감속(정지) → 20초 대기 → 고속 가속 → 80~90 km/h 정속(사인+짧은주기 변동) → 감속.
"""

import csv
import os
import math

SECS_PER_ROW = 0.5
ROWS_PER_MIN = int(60 / SECS_PER_ROW)  # 120

DRIVE_DURATION_SEC = 5 * 60  # 300초

# 구간 (초)
# 시내: 0~25 가속 0→50, 25~55 정속 ~50(변동), 55~70 감속→0
# 정지: 70~90 (20초 신호 대기)
# 고속: 90~115 가속 0→85, 115~275 정속 80~90(변동), 275~300 감속 85→0
CITY_ACCEL_END = 25
CITY_CRUISE_END = 55
CITY_DECEL_END = 70
STOP_END = 90
HWY_ACCEL_END = 115
HWY_CRUISE_END = 275
# 주행 중 DTC 켜짐 시점 (고속 구간 진입 후)
DTC_ON_DRIVING_SEC = 150


def _idle_row(seed_idx, coolant=88.0):
    """공회전 1행: RPM 800~950, speed 0, throttle/load 낮음."""
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


def _driving_speed_at_sec_5min(driving_sec):
    """
    주행 5분(0~300초) 내 목표 속도(km/h).
    시내(가속→정속~50 변동→감속)→정지 20초→고속 가속→정속 80~90 변동→감속.
    정속 구간은 선형이 아니라 사인+짧은 주기로 조금씩 변동.
    """
    if driving_sec < CITY_ACCEL_END:
        return 50.0 * driving_sec / CITY_ACCEL_END
    if driving_sec < CITY_CRUISE_END:
        t = driving_sec - CITY_ACCEL_END
        phase = t / (CITY_CRUISE_END - CITY_ACCEL_END) * 3 * math.pi
        return 50.0 + 2.0 * math.sin(phase) + 0.8 * math.sin(t * 0.5)
    if driving_sec < CITY_DECEL_END:
        t = (driving_sec - CITY_CRUISE_END) / (CITY_DECEL_END - CITY_CRUISE_END)
        return 50.0 * (1.0 - t)
    if driving_sec < STOP_END:
        return 0.0
    if driving_sec < HWY_ACCEL_END:
        return 85.0 * (driving_sec - STOP_END) / (HWY_ACCEL_END - STOP_END)
    if driving_sec < HWY_CRUISE_END:
        t = driving_sec - HWY_ACCEL_END
        phase1 = t / 30.0 * 2 * math.pi
        phase2 = t / 8.0 * 2 * math.pi
        return 85.0 + 3.0 * math.sin(phase1) + 1.2 * math.sin(phase2)
    if driving_sec <= DRIVE_DURATION_SEC:
        t = (driving_sec - HWY_CRUISE_END) / (DRIVE_DURATION_SEC - HWY_CRUISE_END)
        return 85.0 * (1.0 - t)
    return 0.0


def _driving_row(driving_sec, speed_kmh, row_idx):
    """주행 1행: 속도에 맞춘 RPM/부하/스로틀 (속도 올라가면 RPM·부하·스로틀 함께 상승)."""
    rpm = 1200 + speed_kmh * 28 + (row_idx % 5) * 2
    rpm = min(max(int(rpm), 900), 2800)
    coolant = 86.0 + (row_idx % 7) * 0.5
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


def generate_10min_drive_csv():
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "scenario_10min_drive.csv")
    headers = [
        "rpm", "speed", "temp", "load", "voltage", "map", "maf",
        "intake_temp", "throttle", "fuel_trim_short", "fuel_trim_long", "dtcs",
    ]

    rows_off_1 = ROWS_PER_MIN
    rows_idle_2 = 240
    rows_drive = int(DRIVE_DURATION_SEC / SECS_PER_ROW)
    rows_idle_1 = ROWS_PER_MIN
    rows_off_final = ROWS_PER_MIN

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)

        for _ in range(rows_off_1):
            w.writerow(_engine_off_row() + [""])

        for i in range(rows_idle_2):
            w.writerow(_idle_row(i, coolant=52.0 + i * 0.05) + [""])

        stop_row_start = int(CITY_DECEL_END / SECS_PER_ROW)
        stop_row_end = int(STOP_END / SECS_PER_ROW)
        for i in range(rows_drive):
            driving_sec = (i + 1) * SECS_PER_ROW
            dtcs = "P0300" if driving_sec >= DTC_ON_DRIVING_SEC else ""
            if stop_row_start <= i < stop_row_end:
                w.writerow(_idle_row(300 + i, coolant=88.0) + [dtcs])
            else:
                speed = _driving_speed_at_sec_5min(driving_sec)
                w.writerow(_driving_row(driving_sec, speed, i) + [dtcs])

        for i in range(rows_idle_1):
            w.writerow(_idle_row(240 + i, coolant=88.0) + ["P0300"])

        for _ in range(rows_off_final):
            w.writerow(_engine_off_row() + ["P0300"])

    total_rows = rows_off_1 + rows_idle_2 + rows_drive + rows_idle_1 + rows_off_final
    print(f"Generated {path} ({total_rows} rows, 10 min at {SECS_PER_ROW}s interval)")
    print("Phases: 1min OFF, 2min IDLE, 5min DRIVE, 1min IDLE, 1min OFF.")
    return path


if __name__ == "__main__":
    generate_10min_drive_csv()
