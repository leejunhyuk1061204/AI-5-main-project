"""
COM3 시리얼 포트 디버그 모니터
폰에서 블루투스로 보내는 데이터가 실제로 들어오는지 확인
"""
import serial
import time

PORT = "COM3"
BAUD = 38400

print(f"=== COM3 Serial Monitor ===")
print(f"Port: {PORT}, Baud: {BAUD}")
print("Waiting for data... (Ctrl+C to stop)")
print("-" * 40)

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    print(f"[OK] Port opened: {ser.name}")
    
    while True:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting)
            print(f"[RECV] {len(data)} bytes: {data}")
            print(f"[HEX]  {data.hex()}")
            print(f"[STR]  {data.decode('ascii', errors='ignore')}")
        else:
            # 1초마다 상태 출력
            print(f"[WAIT] in_waiting={ser.in_waiting}")
        time.sleep(1)

except serial.SerialException as e:
    print(f"[ERROR] Serial error: {e}")
except KeyboardInterrupt:
    print("\n[STOP] Monitoring stopped")
finally:
    if 'ser' in dir() and ser.is_open:
        ser.close()
        print("[CLOSED] Port closed")
