import yaml
import time
import csv
import threading
import os
import serial
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RobustElmEmulator:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()
        self.connection = self.config.get('connection', {})
        self.port = self.connection.get('port', 'COM3')
        self.baudrate = self.connection.get('baudrate', 38400)
        self.mode = self.config.get('mode', 'static')
        
        # 기본 PIDs (설정 파일에서 덮어씌워짐)
        self.pids = {
            '0100': 'BE 1F B8 10', # Supported PIDs [01-20]
            '010C': '00 00',       # RPM
            '010D': '00',          # Speed
            '0105': '40',          # Coolant
            '0111': '00',          # Throttle
            '0104': '00',          # Engine Load
        }
        self.running = True
        self.ser = None

    def load_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _parse_config_val(self, val):
        """16진수 문자열 또는 정수 숫자를 안전하게 정수로 변환"""
        if isinstance(val, str):
            try:
                return int(val, 16)
            except ValueError:
                return int(val)
        return int(val)

    def initialize_pids(self):
        """설정 파일에서 정적 PID 값을 로드"""
        if self.mode == 'static':
            p_cfg = self.config.get('pids', {})
            logger.info("Loading static PID values from config...")
            
            # RPM (010C): 3000 RPM -> (3000*4) = 12000 (0x2EE0)
            if 'rpm' in p_cfg:
                val = self._parse_config_val(p_cfg['rpm'])
                # 만약 이미 계산된 값(예: 0x2EE0)이 들어왔다면 그대로 쓰고, 
                # RPM 값(예: 3000)이 들어왔다면 *4를 해줍니다.
                if val < 16383: # 대략적인 RPM 범위
                     val = val * 4
                self.pids['010C'] = f"{val >> 8:02X} {val & 0xFF:02X}"
            
            # Speed (010D): A
            if 'speed' in p_cfg:
                val = self._parse_config_val(p_cfg['speed'])
                self.pids['010D'] = f"{val:02X}"
                
            # Coolant (0105): A - 40
            if 'coolant_temp' in p_cfg:
                val = self._parse_config_val(p_cfg['coolant_temp']) + 40
                self.pids['0105'] = f"{val:02X}"
            
            # 나머지 설정들도 필요한 경우 여기에 추가

    def update_from_csv_row(self, row):
        """CSV의 한 줄 데이터를 PID 형식으로 변환"""
        try:
            # 엔진 RPM
            if row.get('Engine RPM [RPM]'):
                rpm_val = int(float(row['Engine RPM [RPM]']) * 4)
                self.pids['010C'] = f"{rpm_val >> 8:02X} {rpm_val & 0xFF:02X}"
            
            # 차속
            if row.get('Vehicle Speed Sensor [km/h]'):
                speed_val = int(float(row['Vehicle Speed Sensor [km/h]']))
                self.pids['010D'] = f"{speed_val:02X}"
            
            # 냉각수 온도
            if row.get('Engine Coolant Temperature [°C]'):
                temp_val = int(float(row['Engine Coolant Temperature [°C]']) + 40)
                self.pids['0105'] = f"{temp_val:02X}"
        except Exception as e:
            logger.debug(f"CSV parsing error: {e}")

    def replay_worker(self):
        """CSV 데이터를 주기적으로 읽어 PIDs 업데이트"""
        csv_cfg = self.config.get('replay', {})
        csv_file = csv_cfg.get('csv_file', 'obd_log.csv')
        csv_path = os.path.join(os.path.dirname(self.config_path), csv_file)
        interval = csv_cfg.get('interval', 0.1)
        
        logger.info(f"Replay worker started using: {csv_file}")
        
        while self.running:
            if not os.path.exists(csv_path):
                logger.error(f"CSV file not found: {csv_path}")
                break
                
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not self.running: break
                    self.update_from_csv_row(row)
                    time.sleep(interval)
            
            if not csv_cfg.get('loop', True):
                break
        logger.info("Replay worker finished.")

    def start(self):
        self.initialize_pids()
        if self.mode == 'replay':
            threading.Thread(target=self.replay_worker, daemon=True).start()

        try:
            # 시리얼 포트 열기
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01)
            logger.info(f"--- Emulator Started on {self.port} @ {self.baudrate} ---")
            logger.info(f"Mode: {self.mode}")
            
            buffer = ""
            while self.running:
                if self.ser.in_waiting > 0:
                    raw_data = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
                    buffer += raw_data
                    
                    if '\r' in buffer:
                        parts = buffer.split('\r')
                        # 마지막 조각은 불완전할 수 있으므로 버퍼에 유지
                        for cmd in parts[:-1]:
                            clean_cmd = cmd.strip().upper().replace(" ", "")
                            if clean_cmd:
                                self.process_command(clean_cmd)
                        buffer = parts[-1]
                time.sleep(0.001)
                
        except Exception as e:
            logger.error(f"FATAL ERROR: {e}")
        finally:
            if self.ser:
                self.ser.close()
                logger.info("Serial port closed.")

    def process_command(self, cmd):
        logger.info(f"-> [RECV] {cmd}")
        
        response = ""
        # 1. AT 명령어 처리
        if cmd.startswith("AT"):
            if cmd == "ATZ": response = "ELM327 v1.5"
            elif cmd == "ATE0": response = "OK"
            elif cmd == "ATL0": response = "OK"
            elif cmd == "ATS0": response = "OK"
            elif cmd == "ATH0": response = "OK"
            elif cmd == "ATSP0": response = "OK"
            else: response = "OK"
            
        # 2. OBD 서비스 01 (실시간 데이터)
        elif cmd.startswith("01"):
            pid = cmd[0:4]
            if pid in self.pids:
                # 41(응답 서비스) + PID + Data
                response = f"41 {pid[2:4]} {self.pids[pid]}"
            else:
                response = "NO DATA"
                
        # 3. 기타 명령어
        else:
            response = "OK"

        if response:
            logger.info(f"<- [SEND] {response}")
            # ELM327 표준 응답 형식: 데이터 + \r + \r + > (프롬프트)
            full_resp = response + "\r\r>"
            self.ser.write(full_resp.encode('ascii'))

if __name__ == "__main__":
    config_file = os.path.join(os.path.dirname(__file__), 'config.yml')
    emulator = RobustElmEmulator(config_file)
    try:
        emulator.start()
    except KeyboardInterrupt:
        emulator.running = False
        print("\nStopping Emulator...")
