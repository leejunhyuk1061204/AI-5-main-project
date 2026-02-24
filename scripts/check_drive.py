
import os
from datetime import datetime

base_path = r"G:\내 드라이브\정비지침서\원본_zip"
try:
    if os.path.exists(base_path):
        files = [f for f in os.listdir(base_path) if f.endswith('.zip')]
        count = len(files)
        print(f"TOTAL_FILES: {count}")
        
        if count > 0:
            # 최근 5개 파일 출력
            file_stats = []
            for f in files:
                path = os.path.join(base_path, f)
                mtime = os.path.getmtime(path)
                file_stats.append((f, mtime))
            
            file_stats.sort(key=lambda x: x[1], reverse=True)
            print("\nLATEST_5_FILES:")
            for name, mtime in file_stats[:5]:
                dt = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{dt} - {name}")
    else:
        print(f"PATH_NOT_FOUND: {base_path}")
        # 루트부터 탐색 시도
        for d in os.listdir("G:\\"):
            print(f"G Drive Root: {d}")
except Exception as e:
    print(f"ERROR: {e}")
