"""
시나리오 1: 정상 주행
시동 걸고 1분 대기 → 5분 주행 → 1분 대기 → 시동 끄기

사용법:
ELM327-emulator 대화형 모드에서:
    exec(open('emulator/scenarios/scenario1_normal_driving.py').read())
    threading.Thread(target=scenario1_normal_driving, daemon=True).start()
"""

import time
import threading
import random


def scenario1_normal_driving():
    """
    정상 주행 시나리오
    - 시동 걸고 1분 대기 (RPM 낮게, 속도 0)
    - 5분 주행 (RPM 높게, 속도 변화)
    - 1분 대기 (RPM 낮게, 속도 0)
    - 시동 끄기
    """
    # 시나리오 시작
    emulator.scenario = "car"
    print("[시나리오 1] 정상 주행 시작")
    
    # RobustElmEmulator 기반: update_pids_from_dict 를 사용해서
    # RPM, 속도, 냉각수 온도, 배터리 전압 등 여러 PID를 함께 갱신한다.

    def update_idle():
        """공회전 상태: 속도 0, 낮은 RPM, 약간의 부하/스로틀, 배터리 전압 안정"""
        coolant = random.uniform(80, 95)  # °C
        emulator.update_pids_from_dict({
            'rpm': random.randint(800, 1000),
            'speed': 0,
            'coolant': coolant,
            'load': random.uniform(10, 25),       # %
            'throttle': random.uniform(5, 15),    # %
            'voltage': random.uniform(13.8, 14.5),# V (배터리/발전기)
            'map': random.uniform(25, 35),        # kPa
            'maf': random.uniform(2.0, 5.0),      # g/s
            'intake_temp': random.uniform(25, 40) # °C
        })

    def update_cruise():
        """정상 주행 상태: 일정/변동 속도, RPM/부하/스로틀 상승"""
        speed = random.randint(40, 100)
        coolant = random.uniform(85, 100)
        emulator.update_pids_from_dict({
            'rpm': random.randint(1500, 3000),
            'speed': speed,
            'coolant': coolant,
            'load': random.uniform(30, 65),       # %
            'throttle': random.uniform(15, 40),   # %
            'voltage': random.uniform(13.5, 14.4),
            'map': random.uniform(40, 80),
            'maf': random.uniform(6.0, 25.0),
            'intake_temp': random.uniform(25, 45)
        })

    # 1단계: 시동 걸고 1분 대기 (RPM 낮게, 속도 0)
    print("[1단계] 시동 걸고 1분 대기 중...")
    start_time = time.time()
    while time.time() - start_time < 60:  # 1분
        update_idle()
        time.sleep(1)

    # 2단계: 5분 주행 (RPM 높게, 속도/부하 변화)
    print("[2단계] 5분 주행 중...")
    start_time = time.time()
    while time.time() - start_time < 300:  # 5분
        update_cruise()
        time.sleep(1)

    # 3단계: 1분 대기 (신호 대기 등, RPM 낮게, 속도 0)
    print("[3단계] 1분 대기 중...")
    start_time = time.time()
    while time.time() - start_time < 60:  # 1분
        update_idle()
        time.sleep(1)

    # 4단계: 시동 끄기 (엔진 런타임/전압만 약간 떨어지는 느낌으로 둠)
    print("[4단계] 시동 끄기")
    emulator.scenario = "engineoff"
    emulator.update_pids_from_dict({
        'rpm': 0,
        'speed': 0,
        'load': 0,
        'throttle': 0,
        'maf': 0,
        'map': 0,
    })

    print("[시나리오 1] 완료")


# 백그라운드 실행을 위한 함수 (직접 호출 가능)
def run():
    """시나리오를 백그라운드 스레드로 실행"""
    threading.Thread(target=scenario1_normal_driving, daemon=True).start()

# 파일 로드 시 자동 실행 (선택사항)
# threading.Thread(target=scenario1_normal_driving, daemon=True).start()
