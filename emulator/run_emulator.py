import yaml
import time
import csv
import threading
import os
import serial
import logging
import requests

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HighMobilityClient:
    """하이모빌리티 API 연동 클라이언트"""
    def __init__(self, token, interval=1.0):
        self.token = token
        self.interval = interval
        self.url = "https://sandbox.api.high-mobility.com/v1/auto_api"
        self.pids_data = {}

    def fetch_data(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        # 필요한 데이터를 한글로 요청하는 GraphQL 쿼리 (또는 REST API)
        # 여기서는 단순화를 위해 전형적인 Auto API 응답을 시뮬레이션하거나 REST 호출
        query = """
        {
          diagnostics {
            engineRPM { value }
            speed { value }
            engineCoolantTemperature { value }
            engineLoad { value }
          }
        }
        """
        try:
            # 실시간 연동을 위해 REST API 사용
            response = requests.post(self.url, headers=headers, json={"query": query}, timeout=10)
            if response.status_code == 200:
                data = response.json().get('data', {}).get('diagnostics', {})
                return {
                    'rpm': data.get('engineRPM', {}).get('value'),
                    'speed': data.get('speed', {}).get('value'),
                    'coolant': data.get('engineCoolantTemperature', {}).get('value'),
                    'load': data.get('engineLoad', {}).get('value')
                }
        except Exception as e:
            logger.error(f"High Mobility API Error: {e}")
        return None

class RobustElmEmulator:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()
        self.connection = self.config.get('connection', {})
        self.port = self.connection.get('port', 'COM3')
        self.baudrate = self.connection.get('baudrate', 38400)
        self.mode = self.config.get('mode', 'static')
        
        # 기본 PIDs
        self.pids = {
            '0100': 'BE 1F B8 10', # Supported PIDs [01-20]
            '010C': '00 00',       # RPM
            '010D': '00',          # Speed
            '0105': '40',          # Coolant
            '0111': '00',          # Throttle
            '0104': '00',          # Engine Load
            '0142': '00 00',       # Control Module Voltage
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
                return int(float(val))
        return int(val)

    def initialize_pids(self):
        """설정 파일에서 정적 PID 값을 로드"""
        if self.mode == 'static':
            p_cfg = self.config.get('pids', {})
            logger.info("Loading static PID values from config...")
            self.update_pids_from_dict({
                'rpm': p_cfg.get('rpm'),
                'speed': p_cfg.get('speed'),
                'coolant': p_cfg.get('coolant_temp'),
                'load': p_cfg.get('engine_load')
            })

    def update_pids_from_dict(self, data):
        """딕셔너리 데이터를 받아서 PID 포맷으로 변환 업데이트"""
        if data.get('rpm') is not None:
            val = int(float(data['rpm']) * 4)
            self.pids['010C'] = f"{val >> 8:02X} {val & 0xFF:02X}"
        if data.get('speed') is not None:
            val = int(float(data['speed']))
            self.pids['010D'] = f"{val:02X}"
        if data.get('coolant') is not None:
            val = int(float(data['coolant']) + 40)
            self.pids['0105'] = f"{val:02X}"
        if data.get('load') is not None:
            val = int(float(data['load']) * 2.55)
            self.pids['0104'] = f"{val:02X}"

    def update_from_csv_row(self, row, mapping):
        """CSV 매핑 설정을 사용하여 데이터 부합 업데이트"""
        try:
            data = {
                'rpm': row.get(mapping.get('rpm')),
                'speed': row.get(mapping.get('speed')),
                'coolant': row.get(mapping.get('coolant_temp')),
                'load': row.get(mapping.get('engine_load')),
                'voltage': row.get(mapping.get('voltage'))
            }
            self.update_pids_from_dict(data)
        except Exception as e:
            logger.debug(f"CSV parsing error: {e}")

    def replay_worker(self):
        """CSV 데이터를 주기적으로 읽어 PIDs 업데이트"""
        csv_cfg = self.config.get('replay', {})
        mapping = csv_cfg.get('mapping', {})
        csv_file = csv_cfg.get('csv_file', 'obd_log.csv')
        csv_path = os.path.join(os.path.dirname(self.config_path), csv_file)
        interval = csv_cfg.get('interval', 0.1)
        
        logger.info(f"Replay worker started using: {csv_file}")
        
        while self.running:
            if not os.path.exists(csv_path):
                logger.error(f"CSV file not found: {csv_path}")
                time.sleep(5)
                continue
                
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not self.running: break
                    self.update_from_csv_row(row, mapping)
                    time.sleep(interval)
            
            if not csv_cfg.get('loop', True):
                break
        logger.info("Replay worker finished.")

    def hm_worker(self):
        """하이모빌리티 데이터 업데이트 워커"""
        hm_cfg = self.config.get('high_mobility', {})
        token = hm_cfg.get('access_token')
        interval = hm_cfg.get('refresh_interval', 1.0)
        
        if not token or "YOUR_HM" in token:
            logger.error("High Mobility Access Token is missing or invalid.")
            return

        client = HighMobilityClient(token, interval)
        logger.info("High Mobility sync worker started.")
        
        while self.running:
            data = client.fetch_data()
            if data:
                self.update_pids_from_dict(data)
            time.sleep(interval)

    def start(self):
        self.initialize_pids()
        if self.mode == 'replay':
            threading.Thread(target=self.replay_worker, daemon=True).start()
        elif self.mode == 'high_mobility':
            threading.Thread(target=self.hm_worker, daemon=True).start()

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
