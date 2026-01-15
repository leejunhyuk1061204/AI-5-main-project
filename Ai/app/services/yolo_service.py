# app/services/yolo_service.py
from ultralytics import YOLO
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
import os

# 1. 모델 경로 설정 (학습 후 생성된 best.pt가 위치할 곳)
MODEL_PATH = "Ai/weights/dashboard/best.pt"

# 서버 시작 시 모델을 미리 메모리에 올려둡니다 (성능 최적화)
if os.path.exists(MODEL_PATH):
    model = YOLO(MODEL_PATH)
else:
    print(f"Warning: {MODEL_PATH}를 찾을 수 없습니다. 학습 전이라면 Mock 모드로 작동합니다.")
    model = None

async def run_yolo_inference(s3_url: str) -> VisualResponse:
    """
    S3 URL 이미지를 받아 YOLOv8 모델로 38개 경고등을 감지합니다.
    """
    # 모델이 아직 준비되지 않았을 경우 (학습 전) 처리
    if model is None:
        # [수정] 테스트를 위해 "경고(WARNING)" 상태를 반환하도록 변경
        return VisualResponse(
            status="WARNING",
            analysis_type="DASHBOARD",
            detected_count=1,
            detections=[
                DetectionItem(
                    label="Check Engine",
                    confidence=0.98,
                    bbox=[100, 100, 50, 50]
                )
            ],
            processed_image_url=s3_url
        )

    # 2. YOLO 추론 실행
    # YOLOv8은 S3 URL이나 웹 주소를 직접 입력받아 분석할 수 있습니다.
    results = model.predict(source=s3_url, save=False, conf=0.25)
    
    detections = []
    
    # 3. 결과 데이터 파싱 (38개 클래스 대응)
    for r in results:
        for box in r.boxes:
            label_idx = int(box.cls[0])      # 모델이 예측한 클래스 번호
            label_name = model.names[label_idx] # Roboflow에서 정의한 이름 (예: 'Check Engine')
            confidence = float(box.conf[0])   # 확신도 (0~1)
            bbox = box.xywh[0].tolist()       # 좌표 [x, y, w, h]

            detections.append(DetectionItem(
                label=label_name,
                confidence=round(confidence, 2),
                bbox=[int(v) for v in bbox]
            ))

    # 4. 최종 응답 생성
    # 경고등이 하나라도 발견되면 "WARNING" 상태로 반환합니다.
    status = "WARNING" if len(detections) > 0 else "NORMAL"
    
    return VisualResponse(
        status=status,
        analysis_type="DASHBOARD",
        detected_count=len(detections),
        detections=detections,
        processed_image_url=s3_url
    )