# app/api/v1/routes/test_router.py
"""
로컬 테스트 라우터 (OpenAI/S3 없이 테스트 가능)
- Mock 응답
- 실제 YOLO 추론 (로컬 이미지)
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from ai.app.services.local_service import process_visual_mock, process_audio_mock
from ai.app.schemas.visual_schema import VisualResponse, DetectionItem
from ai.app.schemas.audio_schema import AudioResponse
from PIL import Image
import io
import os

router = APIRouter(prefix="/test", tags=["Local Test"])


@router.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "OK", "message": "AI Server is running!"}


@router.post("/predict/visual", response_model=VisualResponse)
async def analyze_visual_local(file: UploadFile = File(...)):
    """[Mock] 이미지 파일 직접 수신 -> Mock 응답 반환"""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file type")
    
    content = await file.read()
    return await process_visual_mock(content)


@router.post("/predict/yolo")
async def analyze_yolo_local(file: UploadFile = File(...)):
    """
    [Real YOLO + Mock Anomaly] 로컬 이미지 → YOLO 추론 → 실제 파이프라인 형식 JSON 반환
    실제 /predict/engine과 동일한 형식의 응답을 반환합니다.
    """
    import random
    
    try:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Image file required")
        
        # 이미지 로드
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # YOLO 모델 로드
        from ultralytics import YOLO
        
        model_path = "ai/weights/engine/best.pt"
        if not os.path.exists(model_path):
            model_path = "yolov8n.pt"
            print(f"[Warning] 학습 모델 없음. 기본 모델 사용: {model_path}")
        
        model = YOLO(model_path)
        
        # 추론
        import tempfile
        tmp_path = os.path.join(tempfile.gettempdir(), f"yolo_test_{os.getpid()}.jpg")
        image.save(tmp_path, "JPEG")
        
        try:
            yolo_results = model.predict(source=tmp_path, conf=0.25, save=False)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
        # 결과 파싱
        detections = []
        for r in yolo_results:
            for box in r.boxes:
                label_idx = int(box.cls[0])
                label_name = model.names[label_idx]
                confidence = float(box.conf[0])
                bbox = box.xywh[0].tolist()
                
                detections.append({
                    "label": label_name,
                    "confidence": round(confidence, 3),
                    "bbox": [int(v) for v in bbox]
                })
        
        # EV 부품 체크
        EV_PARTS = {"Inverter", "Electric_Motor", "Charging_Port", "Inverter_Coolant_Reservoir"}
        detected_labels = [d["label"] for d in detections]
        is_ev = any(part in EV_PARTS for part in detected_labels)
        vehicle_type = "EV" if is_ev else "ICE"
        
        # Path A: 부품 감지됨 → Mock Anomaly 분석
        if len(detections) > 0:
            results = []
            anomaly_count = 0
            
            for det in detections:
                # Mock 이상 점수 (실제는 PatchCore가 계산)
                mock_score = round(random.uniform(0.2, 0.9), 2)
                threshold = 0.7
                is_anomaly = mock_score > threshold
                
                if is_anomaly:
                    anomaly_count += 1
                    defect_info = {
                        "defect_category": random.choice(["LEAK", "CORROSION", "WEAR", "CONTAMINATION"]),
                        "defect_label": f"{det['label']}_Defect",
                        "description": f"[Mock] {det['label']}에서 이상이 감지되었습니다.",
                        "severity": random.choice(["MINOR", "WARNING", "CRITICAL"]),
                        "recommended_action": "정비소 점검 권장"
                    }
                else:
                    defect_info = {
                        "defect_category": "NORMAL",
                        "defect_label": "Normal",
                        "description": f"{det['label']}은(는) 정상 상태입니다.",
                        "severity": "NORMAL",
                        "recommended_action": "조치 불필요"
                    }
                
                results.append({
                    "part_name": det["label"],
                    "bbox": det["bbox"],
                    "confidence": det["confidence"],
                    "is_anomaly": is_anomaly,
                    "anomaly_score": mock_score,
                    "threshold": threshold,
                    **defect_info
                })
            
            return JSONResponse(content={
                "status": "SUCCESS",
                "path": "A",
                "source": f"uploaded:{file.filename}",
                "vehicle_type": vehicle_type,
                "parts_detected": len(detections),
                "anomalies_found": anomaly_count,
                "results": results
            })
        
        # Path B: 부품 미감지 → LLM Fallback (Mock)
        else:
            return JSONResponse(content={
                "status": "SUCCESS",
                "path": "B",
                "source": f"uploaded:{file.filename}",
                "vehicle_type": None,
                "parts_detected": 0,
                "llm_analysis": {
                    "type": "VEHICLE",
                    "sub_type": "ENGINE",
                    "status": "NORMAL",
                    "description": "[Mock] 엔진룸 이미지로 보이나 부품을 명확히 감지하지 못했습니다.",
                    "recommendation": "더 선명한 이미지로 재촬영을 권장합니다."
                },
                "is_hard_negative": True
            })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={
            "status": "ERROR",
            "message": str(e)
        }, status_code=500)


@router.post("/predict/audio")
async def analyze_audio_local(file: UploadFile = File(...)):
    """
    [Real AST] 로컬 오디오 업로드 → 실제 AST 추론 → 실제 파이프라인 형식 JSON 반환
    실제 /predict/audio와 동일한 형식의 응답을 반환합니다.
    """
    try:
        # 오디오 파일 확인
        content = await file.read()
        
        # 임시 파일로 저장 (librosa가 파일 경로 필요)
        import tempfile
        import librosa
        import torch
        import torch.nn.functional as F
        
        tmp_path = os.path.join(tempfile.gettempdir(), f"audio_test_{os.getpid()}.wav")
        
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        try:
            # 16kHz로 로드
            audio_array, sr = librosa.load(tmp_path, sr=16000)
            
            # AST 모델 로드
            from transformers import ASTForAudioClassification, ASTFeatureExtractor
            
            model_path = "ai/weights/audio/best_ast_model"
            
            if os.path.exists(model_path):
                model = ASTForAudioClassification.from_pretrained(model_path)
                feature_extractor = ASTFeatureExtractor.from_pretrained(model_path)
                analysis_type = "AST"
            else:
                # 학습된 모델 없으면 Mock 반환
                return JSONResponse(content={
                    "status": "FAULTY",
                    "analysis_type": "AST_MOCK",
                    "category": "ENGINE",
                    "detail": {
                        "diagnosed_label": "Engine_Knocking",
                        "description": "[Mock] 학습된 AST 모델이 없어 Mock 응답을 반환합니다."
                    },
                    "confidence": 0.95,
                    "is_critical": True,
                    "note": f"모델 경로 없음: {model_path}"
                })
            
            # Feature 추출
            inputs = feature_extractor(
                audio_array,
                sampling_rate=16000,
                return_tensors="pt",
                padding="max_length"
            )
            
            # 추론
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probs = F.softmax(logits, dim=-1)
                confidence = probs.max().item()
                predicted_id = logits.argmax(-1).item()
            
            # 라벨 변환
            label_name = model.config.id2label[predicted_id]
            
            # 카테고리 결정
            label_upper = label_name.upper()
            if "ENGINE" in label_upper or "KNOCK" in label_upper or "NORMAL" in label_upper:
                category = "ENGINE"
            elif "BRAKE" in label_upper:
                category = "BRAKES"
            elif "SUSP" in label_upper:
                category = "SUSPENSION"
            else:
                category = "UNKNOWN"
            
            # 상태 결정
            if label_name.upper() == "NORMAL":
                status = "NORMAL"
                is_critical = False
                description = "정상적인 엔진 소리입니다."
            else:
                status = "FAULTY"
                is_critical = True
                description = f"{label_name} 소음이 감지되었습니다. 점검이 필요합니다."
            
            return JSONResponse(content={
                "status": status,
                "analysis_type": analysis_type,
                "category": category,
                "detail": {
                    "diagnosed_label": label_name,
                    "description": description
                },
                "confidence": round(confidence, 4),
                "is_critical": is_critical,
                "source": f"uploaded:{file.filename}"
            })
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={
            "status": "ERROR",
            "message": str(e)
        }, status_code=500)


@router.post("/predict/embedding")
async def get_dummy_embedding(data: dict):
    """[Mock] 더미 임베딩 반환 (1024차원)"""
    text = data.get("text", "")
    dummy_vector = [0.01] * 1024
    
    return {
        "embedding": dummy_vector,
        "model": "mxbai-embed-large-dummy"
    }


@router.get("/endpoints")
async def list_endpoints():
    """사용 가능한 테스트 엔드포인트 목록"""
    return {
        "endpoints": [
            {"path": "/test/health", "method": "GET", "description": "서버 상태 확인"},
            {"path": "/test/predict/yolo", "method": "POST", "description": "실제 YOLO 추론 (이미지 업로드)"},
            {"path": "/test/predict/visual", "method": "POST", "description": "Visual Mock 응답"},
            {"path": "/test/predict/audio", "method": "POST", "description": "Audio Mock 응답"},
        ],
        "usage": {
            "insomnia": {
                "method": "POST",
                "url": "http://localhost:8000/test/predict/yolo",
                "body": "Multipart Form",
                "field": "file = 이미지 파일"
            }
        }
    }
