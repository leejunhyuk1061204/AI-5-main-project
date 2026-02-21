"""
[파일 용도] 중복 데이터 탐지
오디오 데이터셋 내에서 MD5 해시를 기반으로 내용이 완전히 동일한 중복 파일들을 찾아냅니다.
데이터 무결성을 검증하고 정리하는 데 사용됩니다.
"""
import os
import hashlib
from collections import defaultdict

def check_duplicates(root_dir):
    print(f"🔍 Checking for duplicate audio files in: {root_dir}")
    hash_map = defaultdict(list)
    extensions = ('.wav', '.mp3', '.m4a', '.ogg', '.flac')
    
    count = 0
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            if f.lower().endswith(extensions):
                path = os.path.join(root, f)
                hasher = hashlib.md5()
                with open(path, 'rb') as fp:
                    for chunk in iter(lambda: fp.read(4096), b""):
                        hasher.update(chunk)
                h = hasher.hexdigest()
                hash_map[h].append(path)
                count += 1
                if count % 100 == 0:
                    print(f"   Processed {count} files...", end='\r')
    
    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    
    print(f"\n✅ Finished processing {count} files.")
    if not duplicates:
        print("✨ No duplicates found based on MD5 hash.")
    else:
        print(f"⚠️ Found {len(duplicates)} sets of duplicate files:")
        for h, paths in duplicates.items():
            print(f"\nHash: {h}")
            for p in paths:
                print(f"  - {p}")

if __name__ == "__main__":
    check_duplicates("ai/data/audio/train")
