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
    
    # 1단계: 시동 걸고 1분 대기 (RPM 낮게, 속도 0)
    print("[1단계] 시동 걸고 1분 대기 중...")
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(800, 1000))</exec><writeln />'
    emulator.answer['SPEED'] = '<header>7E8</header><size>03</size><data>41 0D 00</data><writeln />'  # 속도 0
    emulator.answer['DTC_STATUS'] = '<header>7E8</header><size>04</size><data>41 01 00 00</data><writeln />'  # 정상 (MIL OFF)
    
    start_time = time.time()
    while time.time() - start_time < 60:  # 1분
        time.sleep(1)
    
    # 2단계: 5분 주행 (RPM 높게, 속도 변화)
    print("[2단계] 5분 주행 중...")
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(1500, 3000))</exec><writeln />'
    emulator.answer['SPEED'] = '<exec>import random; "%.2X" % random.randint(40, 100)</exec><writeln />'
    emulator.answer['DTC_STATUS'] = '<header>7E8</header><size>04</size><data>41 01 00 00</data><writeln />'  # 정상 유지
    
    start_time = time.time()
    while time.time() - start_time < 300:  # 5분
        time.sleep(1)
    
    # 3단계: 1분 대기 (신호 대기 등, RPM 낮게, 속도 0)
    print("[3단계] 1분 대기 중...")
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(800, 1200))</exec><writeln />'
    emulator.answer['SPEED'] = '<header>7E8</header><size>03</size><data>41 0D 00</data><writeln />'  # 속도 0
    
    start_time = time.time()
    while time.time() - start_time < 60:  # 1분
        time.sleep(1)
    
    # 4단계: 시동 끄기
    print("[4단계] 시동 끄기")
    emulator.scenario = "engineoff"
    emulator.answer['RPM'] = '<writeln>NO DATA</writeln>'
    emulator.answer['SPEED'] = '<writeln>NO DATA</writeln>'
    emulator.answer['DTC_STATUS'] = '<writeln>NO DATA</writeln>'
    
    print("[시나리오 1] 완료")


# 백그라운드 실행을 위한 함수 (직접 호출 가능)
def run():
    """시나리오를 백그라운드 스레드로 실행"""
    threading.Thread(target=scenario1_normal_driving, daemon=True).start()

# 파일 로드 시 자동 실행 (선택사항)
# threading.Thread(target=scenario1_normal_driving, daemon=True).start()
