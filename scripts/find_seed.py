
import os

def find_seed_folders(start_path):
    print(f"Searching in: {start_path}")
    try:
        for root, dirs, files in os.walk(start_path):
            # 너무 깊이 들어가지 않도록 제한 (속도 문제)
            depth = root.replace(start_path, '').count(os.sep)
            if depth > 3:
                continue
                
            for d in dirs:
                if 'seed' in d.lower() or '임베딩' in d:
                    full_path = os.path.join(root, d)
                    print(f"FOUND_FOLDER: {full_path}")
                    # 해당 폴더 내 파일들 요약
                    try:
                        f_list = os.listdir(full_path)
                        print(f"  - Files count: {len(f_list)}")
                        for f in f_list[:5]:
                            f_path = os.path.join(full_path, f)
                            size = os.path.getsize(f_path)
                            print(f"  - {f} ({size} bytes)")
                    except:
                        pass
    except Exception as e:
        print(f"ERROR: {e}")

# '내 드라이브' 경로 확인
drive_root = "G:\\"
target_base = ""
for d in os.listdir(drive_root):
    if "드라이브" in d:
        target_base = os.path.join(drive_root, d)
        break

if target_base:
    find_seed_folders(target_base)
else:
    print("Could not find 'Google Drive' root folder.")
