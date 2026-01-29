# ai/app/services/exterior_service.py
"""
외관 파손 분석 서비스 (Exterior Damage Analysis)

[파일 설명]
이 파일은 차량 외관 이미지를 분석하여 파손 부위와 종류를 탐지하는 서비스입니다.
단일 YOLOv8 모델(22개 클래스)을 사용하여 부위와 파손을 동시에 식별합니다.

[API 응답 형식]
{
  "status": "WARNING",
  "analysis_type": "SCENE_EXTERIOR",
  "category": "EXTERIOR",
  "data": {
    "damage_found": true,
    "detections": [{ part, damage_type, confidence, bbox }],
    "description": "앞 범퍼 하단에 긁힘 손상이 있습니다.",
    "repair_estimate": "부분 도색 권장"
  }
}
"""
from typing import List, Optional, Dict, Tuple, Union, Any
from PIL import Image
from ai.app.services.llm_service import analyze_general_image, generate_exterior_report
from ai.app.services.router_service import CONFIDENCE_THRESHOLD
from ai.app.services.yolo_utils import normalize_bbox

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.85

# =============================================================================
# 통합 22종 클래스 매핑 (Label -> {part, damage, severity, description})
# =============================================================================
UNIFIED_CLASSES = {
    # 1. 찌그러짐 (Dent) 계열
    "bonnet-dent": {"part": "본넷(후드)", "damage": "찌그러짐", "severity": "WARNING"},
    "doorouter-dent": {"part": "도어(문)", "damage": "찌그러짐", "severity": "WARNING"},
    "fender-dent": {"part": "펜더", "damage": "찌그러짐", "severity": "WARNING"},
    "front-bumper-dent": {"part": "앞 범퍼", "damage": "찌그러짐", "severity": "WARNING"},
    "quaterpanel-dent": {"part": "쿼터패널", "damage": "찌그러짐", "severity": "WARNING"},
    "rear-bumper-dent": {"part": "뒷 범퍼", "damage": "찌그러짐", "severity": "WARNING"},
    "roof-dent": {"part": "지붕(루프)", "damage": "찌그러짐", "severity": "WARNING"},
    "pillar-dent": {"part": "필러(기둥)", "damage": "찌그러짐", "severity": "CRITICAL"}, # 필러는 주요 골격
    "runningboard-dent": {"part": "런닝보드(사이드스텝)", "damage": "찌그러짐", "severity": "WARNING"},
    "medium-bodypanel-dent": {"part": "차체 패널", "damage": "중형 찌그러짐", "severity": "WARNING"},
    "major-rear-bumper-dent": {"part": "뒷 범퍼", "damage": "심각한 찌그러짐", "severity": "CRITICAL"},

    # 2. 스크래치 (Scratch) 계열
    "doorouter-scratch": {"part": "도어(문)", "damage": "스크래치", "severity": "WARNING"},
    "front-bumper-scratch": {"part": "앞 범퍼", "damage": "스크래치", "severity": "WARNING"},
    "rear-bumper-scratch": {"part": "뒷 범퍼", "damage": "스크래치", "severity": "WARNING"},

    # 3. 유리 및 램프 파손 (Critical)
    "front-windscreen-damage": {"part": "앞 유리", "damage": "유리 파손", "severity": "CRITICAL"},
    "rear-windscreen-damage": {"part": "뒷 유리", "damage": "유리 파손", "severity": "CRITICAL"},
    "headlight-damage": {"part": "헤드라이트", "damage": "파손", "severity": "CRITICAL"},
    "taillight-damage": {"part": "테일램프", "damage": "파손", "severity": "CRITICAL"},
    "sidemirror-damage": {"part": "사이드미러", "damage": "파손", "severity": "WARNING"},
    "signlight-damage": {"part": "방향지시등", "damage": "파손", "severity": "WARNING"},

    # 4. 도장 손상 계열
    "paint-chip": {"part": "차체 전반", "damage": "페인트 벗겨짐", "severity": "WARNING"},
    "paint-trace": {"part": "차체 전반", "damage": "이물질/페인트 자국", "severity": "NORMAL"},
}


async def run_exterior_yolo(
    image: Union[str, Image.Image], 
    model
) -> List[Dict]:
    """단일 YOLO 모델로 통합 파손 분석"""
    detections = []
    
    if model is None:
        return []

    try:
        # YOLOv8 추론
        results = model.predict(source=image, save=False, conf=0.25)
        
        for r in results:
            for box in r.boxes:
                label_idx = int(box.cls[0])
                # 모델의 names 딕셔너리에서 라벨 이름 가져오기
                if hasattr(model, 'names'):
                    raw_label = model.names[label_idx]
                else:
                    raw_label = str(label_idx)
                
                # 라벨 정규화 (대소문자, 특수문자 등을 유연하게 처리)
                # 예: "Front Bear" -> "front-bear", "Front_Bear" -> "front-bear"
                import re
                # 1. 소문자 변환
                normalized_label = raw_label.lower()
                # 2. 알파벳, 숫자 제외한 모든 문자를 하이픈(-)으로 변경
                normalized_label = re.sub(r'[^a-z0-9]+', '-', normalized_label)
                # 3. 양 끝 하이픈 제거
                normalized_label = normalized_label.strip('-')
                
                # 매핑 정보 조회
                info = UNIFIED_CLASSES.get(normalized_label)
                
                # 매핑되지 않은 라벨이 나올 경우의 처리 (Fallback)
                if not info:
                    # 키를 못 찾았을 때를 대비해 유사 매칭 시도 가능하지만, 일단 Unknown 처리
                    # 혹은 names 리스트의 텍스트 그대로 사용
                    info = {
                        "part": "알 수 없음",
                        "damage": raw_label,
                        "severity": "WARNING"
                    }

                detections.append({
                    "part": info["part"],
                    "damage_type": info["damage"],
                    "severity": info["severity"],
                    "confidence": round(float(box.conf[0]), 2),
                    "bbox": [int(v) for v in box.xywh[0].tolist()]
                })

    except Exception as e:
        print(f"[Exterior YOLO Error] {e}")
    
    return detections


async def analyze_exterior_image(
    image: Image.Image,
    s3_url: str, 
    exterior_model=None
) -> Dict[str, Any]:
    """
    외관 파손 분석 메인 함수 (Single Model Version)
    
    Args:
        exterior_model: CarDD+CarParts 통합 YOLO 모델
    """
    # Step 0: 모델 없으면 LLM Fallback
    if exterior_model is None:
        print("[Exterior] YOLO 모델 없음, LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "ERROR",
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": False,
                "detections": [],
                "description": (llm_result.data or {}).get("description", "이미지 분석 실패"),
                "repair_estimate": (llm_result.data or {}).get("recommendation", "전문가 점검 권장"),
                "llm_fallback": True
            }
        }
    
    # Step 1: YOLO 추론
    detections = await run_exterior_yolo(image, exterior_model)
    
    # Step 1-1: 파손이 감지되지 않으면, LLM으로 '진짜 외관인지' + '미세 파손은 없는지' 2차 확인 (Safety Net)
    # Step 1-1: 파손이 감지되지 않으면, LLM으로 '진짜 외관인지' + '미세 파손은 없는지' 2차 확인 (Safety Net)
    if len(detections) == 0:
        print("[Exterior] 감지된 파손 없음. LLM Safety Check 진행.")
        llm_result = await analyze_general_image(s3_url)
        
        status = "UNKNOWN"
        description = "파손이 감지되지 않았으나, 명확한 상태 판단을 위해 AI 정밀 분석이 수행되었습니다."
        
        if hasattr(llm_result, "status"):
            status = llm_result.status
            
        if hasattr(llm_result, "data") and llm_result.data:
            description = llm_result.data.get("description", description)

        # [NEW] 만약 상태가 WARNING/CRITICAL인데 detections가 비어있다면, LLM에게 강제로 라벨링을 요청
        fallback_detections = []
        if status in ["WARNING", "CRITICAL"]:
            print(f"[Exterior] YOLO Miss detected (Status: {status}). Requesting LLM Labeling...")
            from ai.app.services.llm_service import generate_training_labels
            label_result = await generate_training_labels(s3_url, "exterior")
            
            for lbl in label_result.get("labels", []):
                # LLM 라벨을 API detection 포맷으로 변환
                # [Fix] Ratio / Pixel 명시적 구분
                bbox = lbl.get("bbox", [0,0,0,0])
                if all(isinstance(v, float) and 0.0 <= v <= 1.0 for v in bbox):
                    # Ratio -> Pixel 변환
                    w, h = image.width, image.height
                    bbox = [
                        int(bbox[0] * w),
                        int(bbox[1] * h),
                        int(bbox[2] * w),
                        int(bbox[3] * h)
                    ]
                else:
                    # 이미 Pixel 또는 잘못된 값 -> 정수 변환
                    bbox = [int(v) for v in bbox]

                fallback_detections.append({
                    "part": lbl.get("class", "Unknown"),
                    "damage_type": "파손(LLM감지)",
                    "severity": status,
                    "confidence": 0.9, # LLM 판단 신뢰도
                    "bbox": normalize_bbox(lbl["bbox"], image.width, image.height)
                })

        return {
            "status": status,
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": (status != "NORMAL"),
                "detections": fallback_detections,
                "description": description,
                "repair_estimate": (llm_result.data or {}).get("recommendation", "특이사항 없음")
            }
        }
    
    # Step 1-2: 신뢰도 체크
    max_confidence = max(d["confidence"] for d in detections)
    if max_confidence < CONFIDENCE_THRESHOLD:
        print(f"[Exterior] 낮은 신뢰도({max_confidence:.2f}), LLM Fallback")
        llm_result = await analyze_general_image(s3_url)
        return {
            "status": llm_result.status if hasattr(llm_result, 'status') else "WARNING",
            "analysis_type": "SCENE_EXTERIOR",
            "category": "EXTERIOR",
            "data": {
                "damage_found": True,
                "detections": [],
                "description": (llm_result.data or {}).get("description", "신뢰할 수 없는 분석 결과"),
                "repair_estimate": (llm_result.data or {}).get("recommendation", "정교한 재촬영 권장"),
                "llm_fallback": True
            }
        }
    
    # Step 2: 심각도 계산 (가장 높은 심각도 기준)
    severity_rank = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
    max_severity = "NORMAL"
    
    for d in detections:
        current_sev = d["severity"]
        if severity_rank[current_sev] > severity_rank[max_severity]:
            max_severity = current_sev
            
    # Step 3: LLM 리포트 생성
    if max_severity == "NORMAL" and max_confidence >= FAST_PATH_THRESHOLD:
        description = "경미한 흔적이 있으나 수리가 필요한 파손은 감지되지 않았습니다."
        repair_estimate = "별도 조치 불필요"
    else:
        # LLM 전달용 데이터 정제
        mapping_for_llm = []
        for det in detections:
            mapping_for_llm.append({
                "part": det["part"],
                "damage": det["damage_type"],
                "severity": det["severity"]
            })
        
        report = await generate_exterior_report(mapping_for_llm)
        description = report.get("description", "")
        repair_estimate = report.get("recommendation", "")
    
    return {
        "status": max_severity,
        "analysis_type": "SCENE_EXTERIOR",
        "category": "EXTERIOR",
        "data": {
            "damage_found": True,
            "detections": detections,
            "description": description,
            "repair_estimate": repair_estimate
        }
    }
