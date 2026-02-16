import os
import datetime

path = r"G:\내 드라이브\정비지침서\원본_zip"
if os.path.exists(path):
    files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.zip')]
    if files:
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        print(f"Total zip files: {len(files)}")
        print(f"Latest 5 files:")
        for f in files[:5]:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f))
            print(f"  {os.path.basename(f)} - {mtime}")
        
        volvo_files = [f for f in files if 'Volvo' in os.path.basename(f)]
        if volvo_files:
            volvo_files.sort(key=lambda x: os.path.getmtime(x))
            print(f"First Volvo download: {os.path.basename(volvo_files[0])} - {datetime.datetime.fromtimestamp(os.path.getmtime(volvo_files[0]))}")
            print(f"Last Volvo download: {os.path.basename(volvo_files[-1])} - {datetime.datetime.fromtimestamp(os.path.getmtime(volvo_files[-1]))}")
        else:
            print("No Volvo files found.")
    else:
        print(f"No zip files found in {path}")
else:
    print(f"Path does not exist: {path}")
