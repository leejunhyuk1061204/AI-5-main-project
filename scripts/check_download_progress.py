import os
import time

path = r"G:\내 드라이브\정비지침서\원본_zip"
files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.zip')]
if files:
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest = files[0]
    size1 = os.path.getsize(latest)
    print(f"Latest file: {os.path.basename(latest)}")
    print(f"Size 1: {size1/1024/1024:.2f} MB")
    time.sleep(5)
    size2 = os.path.getsize(latest) if os.path.exists(latest) else 0
    print(f"Size 2: {size2/1024/1024:.2f} MB")
    if size2 > size1:
        print("File is growing. Download in progress.")
    else:
        print("File is NOT growing.")
else:
    print("No zip files found.")
