"""
10분 주행 시나리오 CSV 생성 (1+2+5+1+1, 운전점수 감점 최소화)

타임라인:
  0~2초   : 시동 끔 (rpm=0). 앱 주행 시작 조건: RPM>300 연속 4초 → 2초 후 공회전 진입하면 4초 연속 구간 발생
  2초~2분2초 : 시동 켬 + 대기 (공회전, rpm 820~950)
  2분5초~7분5초 : 주행 5분 (시내→신호 정지→고속도로 80~90)
  7분5초~8분5초 : 시동 켬 + 대기 (공회전)
  8분5초~9분5초 : 시동 끔

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
    """공회전 1행: RPM 690~800, speed 0, 스로틀 0. 행마다 1~2 단위 미세 변동."""
    t = seed_idx % 37
    q = seed_idx % 11
    rpm = 692 + (t * 3) % 108 + (q % 3) - 1
    return [
        rpm,
        0,
        round(coolant + (t % 5) * 0.3 + (q % 3) * 0.2 - 0.2, 1),
        15 + (t % 6) + (q % 2) - 0,
        round(13.9 + (t % 4) * 0.1 + (q % 5) * 0.04, 1),
        28 + (t % 5) + (q % 3) - 1,
        round(3.5 + (t % 3) * 0.2 + (q % 4) * 0.1, 1),
        26 + (t % 4) + (q % 3) - 1,
        0,
        (t - 2) % 5 - 2 + (q % 2) - 0,
        (t - 1) % 5 - 2 + (q % 2) - 0,
    ]


def _engine_off_row(seed_idx=0):
    """시동 끔: RPM 0. 행마다 0.5~1 단위 변동."""
    t = seed_idx % 7
    return [0, 0, 84 + (t % 3), 0, round(12.4 + (t % 5) * 0.05, 1), 29 + (t % 3), 0, 34 + (t % 3), 0, 0, 0]


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
    """주행 1행: 고속 max 2200, 사인+행별 1~2 단위 변동."""
    base_rpm = 900 + speed_kmh * 15
    rpm_wave = 80 * math.sin(driving_sec * 0.15) + 40 * math.sin(driving_sec * 0.4)
    rpm = int(base_rpm + rpm_wave + (row_idx % 5) * 3 + (row_idx % 7) - 3)
    rpm = min(max(rpm, 850), 2200)
    coolant = 86.0 + (row_idx % 7) * 0.5 + (row_idx % 5) * 0.2 - 0.4
    load_base = 18.0 + speed_kmh * 0.6
    load_wave = 5 * math.sin(driving_sec * 0.2)
    load = min(70.0, max(10.0, load_base + load_wave + (row_idx % 4) + (row_idx % 3) - 1))
    throttle_base = 12.0 + speed_kmh * 0.45
    throttle_wave = 8 * math.sin(driving_sec * 0.25) + 4 * math.sin(driving_sec * 0.1)
    throttle = min(55.0, max(8.0, throttle_base + throttle_wave + (row_idx % 3) + (row_idx % 4) * 0.5 - 1))
    map_kpa = 32 + int(speed_kmh * 0.6) + (row_idx % 3) + (row_idx % 5) % 2
    map_kpa = min(map_kpa, 80)
    maf = 4.0 + speed_kmh * 0.22 + (row_idx % 3) * 0.1 + (row_idx % 4) * 0.05 - 0.08
    volt = 14.0 + (row_idx % 3) * 0.1 + (row_idx % 7) * 0.02 - 0.06
    intake = 28 + (row_idx % 5) + (row_idx % 4) - 1
    return [
        rpm,
        round(speed_kmh, 1),
        round(coolant, 1),
        round(load, 1),
        round(volt, 1),
        map_kpa,
        round(maf, 1),
        intake,
        round(throttle, 1),
        (row_idx - 1) % 5 - 2 + (row_idx % 2) - 0,
        (row_idx % 5) - 2 + (row_idx % 3) % 2 - 0,
    ]


def generate_10min_drive_csv():
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "scenario_10min_drive.csv")
    headers = [
        "rpm", "speed", "temp", "load", "voltage", "map", "maf",
        "intake_temp", "throttle", "fuel_trim_short", "fuel_trim_long",
        "engine_runtime", "dtcs",
    ]

    # 시나리오 1처럼 첫 행부터 rpm>300(공회전) — 주행 시작/종료·DTC 인식이 안정적으로 동작
    rows_off_1 = 0
    rows_idle_2 = 240
    rows_drive = int(DRIVE_DURATION_SEC / SECS_PER_ROW)
    rows_idle_1 = ROWS_PER_MIN
    rows_off_final = ROWS_PER_MIN

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)

        if rows_off_1 > 0:
            for i in range(rows_off_1):
                w.writerow(_engine_off_row(i) + [0] + [""])

        engine_sec = 0.0
        for i in range(rows_idle_2):
            engine_sec = (i + 1) * SECS_PER_ROW
            w.writerow(_idle_row(i, coolant=52.0 + i * 0.05) + [int(engine_sec)] + [""])

        stop_row_start = int(CITY_DECEL_END / SECS_PER_ROW)
        stop_row_end = int(STOP_END / SECS_PER_ROW)
        for i in range(rows_drive):
            driving_sec = (i + 1) * SECS_PER_ROW
            engine_sec = 120 + driving_sec
            dtcs = "P0300" if driving_sec >= DTC_ON_DRIVING_SEC else ""
            if stop_row_start <= i < stop_row_end:
                w.writerow(_idle_row(300 + i, coolant=88.0) + [int(engine_sec)] + [dtcs])
            else:
                speed = _driving_speed_at_sec_5min(driving_sec)
                w.writerow(_driving_row(driving_sec, speed, i) + [int(engine_sec)] + [dtcs])

        for i in range(rows_idle_1):
            engine_sec = 420 + (i + 1) * SECS_PER_ROW
            w.writerow(_idle_row(240 + i, coolant=88.0) + [int(engine_sec)] + ["P0300"])

        for i in range(rows_off_final):
            w.writerow(_engine_off_row(i) + [0] + ["P0300"])

    total_rows = rows_off_1 + rows_idle_2 + rows_drive + rows_idle_1 + rows_off_final
    print(f"Generated {path} ({total_rows} rows, 10 min at {SECS_PER_ROW}s interval)")
    print("Phases: 0s OFF, 2min IDLE, 5min DRIVE, 1min IDLE, 1min OFF (first row = idle like scenario 1).")
    return path


if __name__ == "__main__":
    generate_10min_drive_csv()
