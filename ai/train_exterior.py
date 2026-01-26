
import os
import shutil
import subprocess
from pathlib import Path

def train_and_move(domain_name, data_yaml, project_path):
    print(f"==================================================")
    print(f"[{domain_name}] 학습 시작...")
    print(f"==================================================")
    
    # 1. 모델 학습 (YOLO CLI 호출)
    # epochs=30, imgsz=640
    cmd = [
        "yolo", "detect", "train",
        f"data={data_yaml}",
        "model=yolov8n.pt",
        "epochs=30",
        "imgsz=640",
        f"project={project_path}",
        "name=train",
        "exist_ok=True" # 덮어쓰기 허용
    ]
    
    print(f"명령어 실행: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[{domain_name}] 학습 중 오류 발생: {e}")
        return

    # 2. 파일 이동
    # 생성 경로: project_path/train/weights/best.pt
    # 목표 경로: project_path/best.pt
    
    source = Path(project_path) / "train" / "weights" / "best.pt"
    destination = Path(project_path) / "best.pt"
    
    if source.exists():
        print(f"[{domain_name}] 학습 완료! 가중치 이동: {source} -> {destination}")
        shutil.copy2(source, destination)
    else:
        print(f"[{domain_name}] 경고: 결과 파일({source})을 찾을 수 없습니다.")

def main():
    root_dir = Path("c:/Users/301/AI-5-main-project")
    weights_dir = root_dir / "ai/weights/exterior"
    
    # 1. CarDD 학습
    train_and_move(
        domain_name="CarDD (파손 감지)",
        data_yaml="ai/data/yolo/exterior/cardd/data.yaml",
        project_path=str(weights_dir / "cardd")
    )
    
    # 2. CarParts 학습
    train_and_move(
        domain_name="CarParts (부위 감지)",
        data_yaml="ai/data/yolo/exterior/carparts/data.yaml",
        project_path=str(weights_dir / "carparts")
    )
    
    print("\n[완료] 모든 학습 및 설정이 끝났습니다.")
    print("이제 서버를 재시작하면 LLM Fallback 없이 YOLO가 작동합니다.")

if __name__ == "__main__":
    main()
