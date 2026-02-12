import yaml
import time
import csv
import threading
import os
import sys
import serial
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RobustElmEmulator:
    def __init__(self, config_path, port_override=None, vehicle_id_override=None):
        self.config_path = config_path
        self.config = self.load_config()
        self.connection = self.config.get('connection', {})
        self.port = port_override or self.connection.get('port', 'COM3')
        self.baudrate = self.connection.get('baudrate', 38400)
        self.mode = self.config.get('mode', 'static')
        vehicle_id = vehicle_id_override or self.config.get('vehicle_id') or self.config.get('default_vehicle_id')
        self.vehicle = self._resolve_vehicle(vehicle_id)
        
        # 기본 PIDs
        self.pids = {
            '0100': 'BE 1F B8 10', # Supported PIDs [01-20]
            '010C': '00 00',       # RPM
            '010D': '00',          # Speed
            '0105': '40',          # Coolant
            '0111': '00',          # Throttle
            '0104': '00',          # Engine Load
            '0142': '00 00',       # Control Module Voltage
            '010B': '00',          # MAP (kPa)
            '0110': '00 00',      # MAF (g/s * 100)
            '010F': '00',          # Intake Temp (offset 40)
            '011F': '00 00',       # Engine Runtime (seconds)
        }
        self.vin = self.vehicle.get('vin', '1HM00000000000001')
        self.calid = self.vehicle.get('calid', '')  # 09 04 응답용 (ASCII 문자열)
        self.cvn = self.vehicle.get('cvn', '')      # 09 06 응답용 (4바이트 hex, 예: "12345678")
        self.dtcs = list(self.vehicle.get('dtcs', []))
        self.mil_on = len(self.dtcs) > 0
        self.voltage = 14.2
        self.engine_start_time = None
        self.running = True
        self.ser = None
        self._first_recv_logged = False

    def _resolve_vehicle(self, vehicle_id):
        """vehicles 리스트에서 vehicle_id에 해당하는 프로필 반환."""
        vehicles = self.config.get('vehicles', [])
        if vehicle_id:
            for v in vehicles:
                if v.get('id') == vehicle_id:
                    return v
        if vehicles:
            return vehicles[0]
        return {}

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

    def _dtc_to_hex(self, code):
        """OBD-II DTC 코드(P0115 등)를 2바이트 (b1, b2)로 변환."""
        if not code or len(code) < 4:
            return (0x00, 0x00)
        prefix = code[0].upper()
        num_str = code[1:].strip()
        prefix_val = {'P': 0x0, 'C': 0x1, 'B': 0x2, 'U': 0x3}.get(prefix, 0x0)
        try:
            if all(c in '0123456789ABCDEFabcdef' for c in num_str):
                num = int(num_str, 16)
            else:
                num = int(num_str)
        except ValueError:
            return (0x00, 0x00)
        num = num & 0x3FFF
        b1 = (prefix_val << 6) | (num >> 8)
        b2 = num & 0xFF
        return (b1, b2)

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
            self.pids['0104'] = f"{min(val, 255):02X}"
        if data.get('map') is not None:
            val = int(float(data['map']))
            self.pids['010B'] = f"{min(max(val, 0), 255):02X}"
        if data.get('maf') is not None:
            val = int(float(data['maf']) * 100)
            val = min(max(val, 0), 0xFFFF)
            self.pids['0110'] = f"{val >> 8:02X} {val & 0xFF:02X}"
        if data.get('intake_temp') is not None:
            val = int(float(data['intake_temp']) + 40)
            self.pids['010F'] = f"{min(max(val, 0), 255):02X}"
        if data.get('engine_runtime') is not None:
            val = int(float(data['engine_runtime']))
            val = min(max(val, 0), 0xFFFF)
            self.pids['011F'] = f"{val >> 8:02X} {val & 0xFF:02X}"
        if data.get('voltage') is not None:
            val = int(float(data['voltage']) * 1000)
            val = min(max(val, 0), 0xFFFF)
            self.pids['0142'] = f"{val >> 8:02X} {val & 0xFF:02X}"
        if data.get('throttle') is not None:
            val = int(float(data['throttle']) * 2.55)
            self.pids['0111'] = f"{min(max(val, 0), 255):02X}"

    _PID_TO_KEY = {
        '010C': 'rpm', '010D': 'speed', '0105': 'coolant', '0104': 'load',
        '0142': 'voltage', '0111': 'throttle', '010B': 'map', '0110': 'maf',
        '010F': 'intake_temp', '011F': 'engine_runtime',
    }

    def update_from_csv_row(self, row, mappings):
        """mappings: PID -> { col, formula }. CSV row에서 값을 꺼내 formula 적용 후 PIDs 업데이트."""
        if not mappings:
            return
        data = {}
        for pid, m in mappings.items():
            col = m.get('col')
            if not col or col not in row:
                continue
            try:
                x = float(row[col])
                formula = m.get('formula', 'x')
                result = eval(formula, {'x': x})
                key = self._PID_TO_KEY.get(pid)
                if key:
                    data[key] = result
            except (ValueError, TypeError) as e:
                logger.debug(f"CSV mapping {pid} col={col}: {e}")
        if data:
            self.update_pids_from_dict(data)

    def replay_worker(self):
        """선택된 차량의 CSV를 주기적으로 읽어 PIDs 업데이트"""
        replay_cfg = self.config.get('replay', {})
        csv_file = self.vehicle.get('csv_file', replay_cfg.get('csv_file', 'obd_log.csv'))
        mappings = self.vehicle.get('mappings', {})
        base_dir = os.path.dirname(os.path.abspath(self.config_path))
        csv_path = os.path.join(base_dir, csv_file)
        interval = replay_cfg.get('interval', 0.1)
        loop = replay_cfg.get('loop', True)
        logger.info(f"Replay worker started: vehicle={self.vehicle.get('name', '?')}, csv={csv_file}")
        while self.running:
            if not os.path.exists(csv_path):
                logger.error(f"CSV file not found: {csv_path}")
                time.sleep(5)
                continue
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not self.running:
                        break
                    self.update_from_csv_row(row, mappings)
                    time.sleep(interval)
            if not loop:
                break
        logger.info("Replay worker finished.")

    def _runtime_worker(self):
        """Engine Runtime(011F)을 1초마다 경과 시간으로 업데이트"""
        while self.running:
            if self.engine_start_time is not None:
                runtime = int(time.time() - self.engine_start_time)
                runtime = min(runtime, 0xFFFF)
                self.pids['011F'] = f"{runtime >> 8:02X} {runtime & 0xFF:02X}"
            time.sleep(1)

    def start(self):
        self.initialize_pids()
        self.engine_start_time = time.time()
        threading.Thread(target=self._runtime_worker, daemon=True).start()
        if self.mode == 'replay':
            threading.Thread(target=self.replay_worker, daemon=True).start()

        try:
            # 시리얼 포트 열기
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01)
            logger.info(f"--- Emulator Started on {self.port} @ {self.baudrate} ---")
            logger.info(f"Mode: {self.mode} | Vehicle: {self.vehicle.get('name', self.vehicle.get('id', '?'))}")
            logger.info(f"Waiting for incoming SPP connection on {self.port} (connect from phone)...")

            buffer = ""
            while self.running:
                if self.ser.in_waiting > 0:
                    raw_data = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
                    if not self._first_recv_logged:
                        self._first_recv_logged = True
                        logger.info("*** First data received - client connected ***")
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
            elif cmd == "ATRV": response = f"{self.voltage:.1f}V"
            elif cmd == "ATDP": response = "ISO 15765-4 (CAN 11/500)"
            elif cmd == "ATDPN": response = "6"
            else: response = "OK"
            
        # 2. OBD 서비스 01 (실시간 데이터)
        elif cmd.startswith("01"):
            pid = cmd[0:4]
            if pid == "0101":
                # MIL 상태 및 DTC 개수
                # Byte A: bit 7 = MIL status, bits 0-6 = number of DTCs
                dtc_count = len(self.dtcs) & 0x7F
                byte_a = (0x80 if self.mil_on else 0x00) | dtc_count
                # 응답: 41 01 [Byte A] [Byte B] [Byte C] [Byte D]
                # B, C, D는 보통 테스트 완료 상태 등을 나타냄 (여기서는 00 처리)
                response = f"41 01 {byte_a:02X} 00 00 00"
            elif pid in self.pids:
                # 41(응답 서비스) + PID + Data
                response = f"41 {pid[2:4]} {self.pids[pid]}"
            else:
                response = "NO DATA"

        # 2.5 Mode 02 (Freeze Frame DTC)
        elif cmd == "020200":
            if not self.dtcs:
                response = "NO DATA"
            else:
                b1, b2 = self._dtc_to_hex(self.dtcs[0])
                response = f"42 02 00 {b1:02X} {b2:02X}"

        # 3. OBD 서비스 03 (저장된 DTC 조회)
        elif cmd == "03":
            if not self.dtcs:
                response = "43 00 00 00 00 00 00"
            else:
                hex_dtcs = []
                for code in self.dtcs[:3]:
                    b1, b2 = self._dtc_to_hex(code)
                    hex_dtcs.append(f"{b1:02X} {b2:02X}")
                while len(hex_dtcs) < 3:
                    hex_dtcs.append("00 00")
                response = f"43 {' '.join(hex_dtcs)}"

        # 4. OBD 서비스 04 (DTC 삭제)
        elif cmd == "04":
            logger.info(" Clearing DTCs...")
            self.dtcs = []
            self.mil_on = False
            response = "44"

        # 5. OBD 서비스 07 (보류 중인 DTC 조회)
        elif cmd == "07":
            # 여기선 간단히 03과 동일하게 처리하거나 빈 응답
            response = "47 00 00 00 00 00 00"

        # 6. OBD 서비스 09 (차량 정보) — 차량 특정 로직(VIN/CALID/CVN) 테스트용
        elif cmd.startswith("0902"):
            vin_hex = " ".join([f"{ord(c):02X}" for c in self.vin])
            response = f"49 02 01 {vin_hex}"
        elif cmd.startswith("0904"):
            # CALID: ASCII 문자열을 16진수로 (최대 4바이트 등 단위는 ECU에 따름)
            if self.calid:
                calid_hex = " ".join([f"{ord(c):02X}" for c in self.calid[:16]])
                response = f"49 04 01 {calid_hex}"
            else:
                response = "NO DATA"
        elif cmd.startswith("0906"):
            # CVN: 4바이트 hex (공백 제거 후 8자 hex를 "XX XX XX XX" 형태로)
            if self.cvn:
                cvn_clean = self.cvn.replace(" ", "").upper()[:8].ljust(8, "0")
                if len(cvn_clean) >= 8:
                    response = f"49 06 01 {cvn_clean[0:2]} {cvn_clean[2:4]} {cvn_clean[4:6]} {cvn_clean[6:8]}"
                else:
                    response = "NO DATA"
            else:
                response = "NO DATA"

        # 7. 기타 명령어
        else:
            response = "OK"

        if response:
            logger.info(f"<- [SEND] {response}")
            # ELM327 표준 응답 형식: 데이터 + \r + \r + > (프롬프트)
            full_resp = response + "\r\r>"
            self.ser.write(full_resp.encode('ascii'))

def _parse_args():
    port = None
    vehicle = None
    config_file = os.path.join(os.path.dirname(__file__), 'config.yml')
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--port' and i + 1 < len(sys.argv):
            port = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] in ('--vehicle', '-v') and i + 1 < len(sys.argv):
            vehicle = sys.argv[i + 1]
            i += 2
        elif sys.argv[i].endswith('.yml') or sys.argv[i].endswith('.yaml'):
            config_file = sys.argv[i]
            i += 1
        else:
            i += 1
    return config_file, port, vehicle


if __name__ == "__main__":
    config_file, port_override, vehicle_override = _parse_args()
    emulator = RobustElmEmulator(config_file, port_override=port_override, vehicle_id_override=vehicle_override)
    try:
        emulator.start()
    except KeyboardInterrupt:
        emulator.running = False
        print("\nStopping Emulator...")
