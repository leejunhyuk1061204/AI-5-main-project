import subprocess
import time
import os

def run_parser():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting parser...")
    subprocess.run(["python", "scripts/parse_manuals_to_json.py"])

def main():
    print("Background Parser Looper Started.")
    try:
        while True:
            run_parser()
            print("Waiting 30 seconds for next parse cycle...")
            time.sleep(30) # 30초 대기 (다운로더 속도에 맞춤)
    except KeyboardInterrupt:
        print("Looper stopped.")

if __name__ == "__main__":
    main()
