"""
시나리오 2: 고장 발생 시나리오
시동 걸고 30초 주행 → 2분 주행 → DTC 발생 → 갓길에 세워서 1분 대기 → 시동 끄기

사용법:
ELM327-emulator 대화형 모드에서:
    exec(open('emulator/scenarios/scenario2_dtc_failure.py').read())
    threading.Thread(target=scenario2_dtc_failure, daemon=True).start()
"""

import time
import threading
import random


def scenario2_dtc_failure():
    """
    고장 발생 시나리오
    - 시동 걸고 30초 주행
    - 2분 추가 주행
    - DTC 고장 코드 발생 (MIL 켜짐)
    - 갓길에 세워서 1분 대기
    - 시동 끄기
    """
    # 시나리오 시작
    emulator.scenario = "car"
    print("[시나리오 2] 고장 발생 시나리오 시작")
    
    # 1단계: 시동 걸고 30초 주행
    print("[1단계] 시동 걸고 30초 주행 중...")
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(1500, 2500))</exec><writeln />'
    emulator.answer['SPEED'] = '<exec>import random; "%.2X" % random.randint(40, 80)</exec><writeln />'
    emulator.answer['DTC_STATUS'] = '<header>7E8</header><size>04</size><data>41 01 00 00</data><writeln />'  # 정상 (MIL OFF)
    
    start_time = time.time()
    while time.time() - start_time < 30:  # 30초
        time.sleep(1)
    
    # 2단계: 2분 더 주행
    print("[2단계] 2분 추가 주행 중...")
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(1500, 2800))</exec><writeln />'
    emulator.answer['SPEED'] = '<exec>import random; "%.2X" % random.randint(50, 100)</exec><writeln />'
    emulator.answer['DTC_STATUS'] = '<header>7E8</header><size>04</size><data>41 01 00 00</data><writeln />'  # 정상 유지
    
    start_time = time.time()
    while time.time() - start_time < 120:  # 2분
        time.sleep(1)
    
    # 3단계: DTC 발생! (MIL 켜짐, 고장 코드 저장됨)
    print("[3단계] ⚠️ DTC 고장 코드 발생!")
    
    # DTC 상태: MIL ON (33), DTC 저장됨
    # 41 01 33 00 = Mode 01 PID 01 응답, MIL ON (33), DTC 개수 0 (실제로는 4개 있음)
    emulator.answer['DTC_STATUS'] = '<header>7E8</header><size>04</size><data>41 01 33 00</data><writeln />'
    
    # 실제 DTC 코드들 (일어날 법한 고장들)
    # Mode 03 응답: 43 04 03 01 01 71 04 20 01 28
    # - P0301: 실린더 1 미스파이어 (흔한 고장)
    # - P0171: 시스템 너무 희박 (Bank 1) - 연료/공기 비율 문제
    # - P0420: 촉매 변환기 효율 저하 (Bank 1) - 배기 시스템 문제
    # - P0128: 냉각수 온도 센서 범위/성능 문제
    emulator.answer['DTC_CODES'] = '<header>7E8</header><size>10</size><data>43 04 03 01 01 71 04 20 01 28</data><writeln />'
    
    # 고장 발생 후 RPM 불안정하게 (떨어짐)
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(1000, 2000))</exec><writeln />'  # RPM 떨어짐
    emulator.answer['SPEED'] = '<exec>import random; "%.2X" % random.randint(0, 30)</exec><writeln />'  # 속도 감소
    
    # 4단계: 갓길에 세워서 1분 대기
    print("[4단계] 갓길에 세워서 1분 대기 중...")
    emulator.answer['RPM'] = '<exec>import random; "%.4X" % int(4 * random.randint(800, 1000))</exec><writeln />'
    emulator.answer['SPEED'] = '<header>7E8</header><size>03</size><data>41 0D 00</data><writeln />'  # 속도 0
    # DTC는 계속 유지됨
    
    start_time = time.time()
    while time.time() - start_time < 60:  # 1분
        time.sleep(1)
    
    # 5단계: 시동 끄기
    print("[5단계] 시동 끄기")
    emulator.scenario = "engineoff"
    emulator.answer['RPM'] = '<writeln>NO DATA</writeln>'
    emulator.answer['SPEED'] = '<writeln>NO DATA</writeln>'
    emulator.answer['DTC_STATUS'] = '<writeln>NO DATA</writeln>'
    emulator.answer['DTC_CODES'] = '<writeln>NO DATA</writeln>'
    
    print("[시나리오 2] 완료")


# 백그라운드 실행을 위한 함수 (직접 호출 가능)
def run():
    """시나리오를 백그라운드 스레드로 실행"""
    threading.Thread(target=scenario2_dtc_failure, daemon=True).start()

# 파일 로드 시 자동 실행 (선택사항)
# threading.Thread(target=scenario2_dtc_failure, daemon=True).start()
