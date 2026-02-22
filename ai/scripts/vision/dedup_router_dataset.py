# ai/scripts/vision/dedup_router_dataset.py
"""
Router 데이터셋 중복 검사 및 제거 스크립트

[역할]
1. train/val/test 세트 간 파일명 + 이미지 해시(MD5) 기반 중복 검출
2. 중복 발견 시 val/test에서 우선 유지, train에서 제거 (테스트 데이터 보존)
3. --dry-run으로 미리 확인 가능

[사용법]
  검사만:   python dedup_router_dataset.py --dry-run
  실제 제거: python dedup_router_dataset.py
  
[우선순위]
  test > val > train (test 데이터는 절대 삭제 안 함)
"""
import os
import hashlib
import argparse
from collections import defaultdict

# [Path Config] RunPod과 로컬 환경 자동 감지
RUNPOD_DATA_PATH = "/workspace/large_data"
LOCAL_DATA_PATH = "ai/data"
DATA_ROOT = RUNPOD_DATA_PATH if os.path.exists(RUNPOD_DATA_PATH) else LOCAL_DATA_PATH
DATA_DIR = os.path.join(DATA_ROOT, "yolo_router")

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff'}

# 우선순위: test > val > train (숫자가 높을수록 보존)
SPLIT_PRIORITY = {"test": 3, "val": 2, "train": 1}


def get_file_hash(path):
    """파일 내용의 MD5 해시 계산"""
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def scan_dataset(data_dir):
    """데이터셋 스캔 → {split: {class: [파일 경로]}}"""
    dataset = {}
    for split in ["train", "val", "test"]:
        split_dir = os.path.join(data_dir, split)
        if not os.path.exists(split_dir):
            continue
        dataset[split] = {}
        for cls_name in sorted(os.listdir(split_dir)):
            cls_dir = os.path.join(split_dir, cls_name)
            if not os.path.isdir(cls_dir):
                continue
            files = [
                os.path.join(cls_dir, f) for f in os.listdir(cls_dir)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTS
            ]
            dataset[split][cls_name] = files
    return dataset


def find_duplicates(dataset):
    """
    이미지 해시 기반 중복 검출
    Returns: [(keep_path, remove_path, reason), ...]
    """
    # 1. 모든 파일의 해시 계산
    hash_map = defaultdict(list)  # hash -> [(split, class, path), ...]
    
    total_files = sum(len(files) for split in dataset.values() for files in split.values())
    print(f"\n🔍 Scanning {total_files} images for duplicates...")
    
    scanned = 0
    for split, classes in dataset.items():
        for cls_name, files in classes.items():
            for path in files:
                file_hash = get_file_hash(path)
                hash_map[file_hash].append((split, cls_name, path))
                scanned += 1
                if scanned % 200 == 0:
                    print(f"   Scanned: {scanned}/{total_files}", end="\r", flush=True)
    
    print(f"   Scanned: {scanned}/{total_files} ✅")
    
    # 2. 중복 그룹 찾기
    duplicates_to_remove = []
    dup_groups = {h: entries for h, entries in hash_map.items() if len(entries) > 1}
    
    if not dup_groups:
        print("✅ 중복 없음! 모든 이미지가 고유합니다.")
        return []
    
    print(f"\n⚠️ {len(dup_groups)}개 중복 그룹 발견!\n")
    
    for file_hash, entries in dup_groups.items():
        # 우선순위로 정렬 (test > val > train)
        entries.sort(key=lambda x: SPLIT_PRIORITY.get(x[0], 0), reverse=True)
        
        # 첫 번째(최고 우선순위)는 유지, 나머지 제거
        keep = entries[0]
        for remove in entries[1:]:
            reason = f"동일 이미지: {keep[0]}/{keep[1]} 에 이미 존재"
            duplicates_to_remove.append((keep[2], remove[2], reason))
    
    return duplicates_to_remove


def print_report(dataset, duplicates):
    """현재 상태 + 중복 정보 출력"""
    print(f"\n{'='*70}")
    print(f"📊 Router Dataset Report")
    print(f"{'='*70}")
    
    # 현재 분포
    print(f"\n[현재 분포]")
    print(f"{'Split':<8} {'dashboard':>10} {'engine':>10} {'exterior':>10} {'tire':>10} {'Total':>10}")
    print("-" * 60)
    
    for split in ["train", "val", "test"]:
        if split not in dataset:
            continue
        counts = {cls: len(files) for cls, files in dataset[split].items()}
        total = sum(counts.values())
        print(f"{split:<8} {counts.get('dashboard', 0):>10} {counts.get('engine', 0):>10} "
              f"{counts.get('exterior', 0):>10} {counts.get('tire', 0):>10} {total:>10}")
    
    # 중복 상세
    if duplicates:
        print(f"\n[중복 목록] ({len(duplicates)}개 제거 대상)")
        print("-" * 70)
        
        # 요약: split별 제거 수
        remove_by_split = defaultdict(int)
        for keep_path, remove_path, reason in duplicates:
            # split 추출
            rel = os.path.relpath(remove_path, DATA_DIR)
            split = rel.split(os.sep)[0]
            remove_by_split[split] += 1
        
        for split, count in sorted(remove_by_split.items()):
            print(f"   {split}: {count}개 제거 예정")
        
        # 상세 (최대 20개만)
        print(f"\n   상세 (상위 20건):")
        for i, (keep, remove, reason) in enumerate(duplicates[:20]):
            keep_rel = os.path.relpath(keep, DATA_DIR)
            remove_rel = os.path.relpath(remove, DATA_DIR)
            print(f"   {i+1:3d}. ❌ {remove_rel}")
            print(f"        → 유지: {keep_rel}")
        
        if len(duplicates) > 20:
            print(f"   ... 외 {len(duplicates) - 20}건")


def remove_duplicates(duplicates, dry_run=True):
    """중복 파일 제거"""
    if dry_run:
        print(f"\n🏷️ [DRY RUN] {len(duplicates)}개 파일을 제거할 예정입니다.")
        print(f"   실제 삭제하려면 --dry-run 없이 실행하세요.")
        return 0
    
    removed = 0
    for keep_path, remove_path, reason in duplicates:
        try:
            os.remove(remove_path)
            removed += 1
        except Exception as e:
            print(f"   ⚠️ 삭제 실패: {remove_path} ({e})")
    
    print(f"\n✅ {removed}개 중복 파일 제거 완료!")
    return removed


def main():
    parser = argparse.ArgumentParser(description="Router 데이터셋 중복 검사 및 제거")
    parser.add_argument("--dry-run", action="store_true", help="실제 삭제 없이 검사만")
    parser.add_argument("--data-dir", type=str, default=DATA_DIR, help=f"데이터 경로 (default: {DATA_DIR})")
    args = parser.parse_args()
    
    data_dir = args.data_dir
    
    print(f"📂 Data Directory: {data_dir}")
    
    if not os.path.exists(data_dir):
        print(f"❌ 데이터 경로가 존재하지 않습니다: {data_dir}")
        return
    
    # 1. 스캔
    dataset = scan_dataset(data_dir)
    
    # 2. 중복 검출
    duplicates = find_duplicates(dataset)
    
    # 3. 리포트
    print_report(dataset, duplicates)
    
    # 4. 제거
    if duplicates:
        remove_duplicates(duplicates, dry_run=args.dry_run)
    
    # 5. 제거 후 분포 (실제 삭제한 경우만)
    if duplicates and not args.dry_run:
        print(f"\n[제거 후 분포]")
        dataset_after = scan_dataset(data_dir)
        print_report(dataset_after, [])


if __name__ == "__main__":
    main()
