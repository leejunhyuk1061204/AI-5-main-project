import subprocess
import sys
import os
import time
from datetime import datetime

LOG_FILE = "data/logs/pipeline.log"
STATUS_FILE = "data/logs/status.txt"

def log_and_print(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    full_message = f"{timestamp} {message}"
    print(full_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(full_message + "\n")

def update_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nStatus: {status}")

def run_script(script_name):
    log_and_print(f"Starting Stage: {script_name}")
    update_status(f"Running {script_name}...")
    
    # 실시간 출력을 위해 PGPNT 사용 (stdout, stderr 모두 캡처)
    process = subprocess.Popen(
        [sys.executable, f"scripts/{script_name}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="cp949",
        errors="replace",
        bufsize=1
    )
    
    # 실시간으로 한 줄씩 읽어서 로그에 기록
    for line in process.stdout:
        print(line, end="") # 터미널 출력
        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(line)
            
    process.wait()
    
    if process.returncode != 0:
        log_and_print(f"Error occurred in {script_name}. Pipeline stopped.")
        update_status(f"FAILED at {script_name}")
        return False
    
    log_and_print(f"Finished Stage: {script_name}")
    return True

def main():
    os.makedirs("data/logs", exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Pipeline Session Started: {datetime.now()} ===\n")

    stages = [
        "download_bulk_manuals.py",
        "parse_manuals_to_json.py",
        "incremental_embedder.py"
    ]
    
    for stage in stages:
        if not run_script(stage):
            sys.exit(1)

    log_and_print("ALL STAGES COMPLETED SUCCESSFULLY!")
    update_status("ALL COMPLETED")

if __name__ == "__main__":
    main()
