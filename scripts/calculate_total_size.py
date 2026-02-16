import os

path = r"G:\내 드라이브\정비지침서\원본_zip"
if os.path.exists(path):
    total_size = sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path) if f.endswith('.zip'))
    file_count = len([f for f in os.listdir(path) if f.endswith('.zip')])
    avg_size = total_size / file_count / 1024 / 1024 if file_count > 0 else 0
    print(f"Total size: {total_size / 1024 / 1024 / 1024:.2f} GB")
    print(f"File count: {file_count}")
    print(f"Average size: {avg_size:.2f} MB")
else:
    print("Path not found")
