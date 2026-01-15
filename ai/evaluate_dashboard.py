from ultralytics import YOLO
import os

# -----------------------------------------------------------------------------
# [설정] 평가할 모델 및 데이터 경로
# -----------------------------------------------------------------------------
# 1. 평가할 모델 파일 경로
MODEL_PATH = "Ai/weights/dashboard/best.pt"

# 2. 평가할 데이터셋 정보 파일 (data.yaml)
# 학습 때 Roboflow로 다운로드 받은 폴더 안에 있습니다.
# 예: "./car-dashboard-3/data.yaml"
# (주의: 만약 폴더명이 바뀌었다면 실제 경로로 수정해주세요)
DATA_YAML_PATH = "./car-dashboard-3/data.yaml"

# -----------------------------------------------------------------------------
# 검증 로직 실행
# -----------------------------------------------------------------------------
def run_evaluation():
    if not os.path.exists(MODEL_PATH):
        print(f"[Error] 모델 파일이 없습니다: {MODEL_PATH}")
        print(" -> 먼저 train_dashboard.py를 실행해서 모델을 학습시켜주세요.")
        return

    if not os.path.exists(DATA_YAML_PATH):
        print(f"[Error] 데이터셋 설정 파일이 없습니다: {DATA_YAML_PATH}")
        print(" -> train_dashboard.py를 한 번 실행해서 데이터를 다운로드 받거나, 경로를 확인해주세요.")
        return

    print(f"[Info] 모델 로드 중: {MODEL_PATH}")
    try:
        model = YOLO(MODEL_PATH)

        print("[Info] 성능 평가 시작 (Test Set)...")
        # split='test'는 데이터셋에 test 항목이 있을 때만 동작합니다.
        # 만약 test가 없다면 split='val'로 바꿔주세요.
        metrics = model.val(data=DATA_YAML_PATH, split='test')

        print("\n" + "="*30)
        print(f"🎯 mAP50-95 (종합 점수): {metrics.box.map:.4f}")
        print(f"🎯 mAP50    (감지 정확도): {metrics.box.map50:.4f}")
        print("="*30 + "\n")

    except Exception as e:
        print(f"[Error] 평가 중 오류 발생: {e}")

if __name__ == "__main__":
    run_evaluation()
