import os
import shutil
import random
from pathlib import Path

def split_test_dataset(base_path, test_ratio=0.15):
    """
    각 부품 폴더의 train 데이터 중 일부를 test 폴더로 이동시킵니다.
    """
    base_dir = Path(base_path)
    if not base_dir.exists():
        print(f"[ERROR] 경로가 존재하지 않습니다: {base_path}")
        return

    # 가공할 부품 폴더 리스트 (데이터가 있는 폴더만)
    components = [d for d in base_dir.iterdir() if d.is_dir()]
    
    for comp_dir in components:
        print(f"\n>>> Processing: {comp_dir.name}")
        train_dir = comp_dir / "train"
        test_dir = comp_dir / "test"

        if not train_dir.exists():
            print(f"  [SKIP] train 폴더가 없습니다.")
            continue

        for cls_name in ["normal", "abnormal"]:
            src_path = train_dir / cls_name
            dst_path = test_dir / cls_name

            if not src_path.exists():
                print(f"  [SKIP] {cls_name} 폴더가 없습니다.")
                continue

            # 대상 폴더 생성
            dst_path.mkdir(parents=True, exist_ok=True)

            # 파일 리스트 확보
            files = [f for f in src_path.iterdir() if f.is_file()]
            if not files:
                print(f"  [EMPTY] {cls_name} 폴더에 파일이 없습니다.")
                continue

            # 이동할 파일 개수 계산 (최소 1장)
            num_test = max(1, int(len(files) * test_ratio))
            test_samples = random.sample(files, num_test)

            print(f"  [{cls_name}] {len(files)}장 중 {len(test_samples)}장을 test 폴더로 이동합니다.")

            # 파일 이동
            for f in test_samples:
                shutil.move(str(f), str(dst_path / f.name))

    print("\n[DONE] Dataset splitting completed successfully.")

if __name__ == "__main__":
    # 데이터셋 경로 설정
    DATA_PATH = r"C:\Users\301\Desktop\data\classification"
    split_test_dataset(DATA_PATH)
