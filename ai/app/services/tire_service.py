# ai/app/services/tire_service.py
"""
타이어 분석 서비스 (Tire Analysis)

[파일 설명]
이 파일은 타이어 이미지를 분석하여 마모도(%)와 위험 상태를 탐지하는 서비스입니다.

[핵심 설계: YOLO + LLM 협업]
┌─────────────────────────────────────────────────────────────────┐
│ 데이터셋 현황:                                                   │
│ - Tire YOLO 데이터셋: normal / worn 2클래스만 있음               │
│ - crack, flat, bulge, uneven 등 세부 클래스 없음                 │
│                                                                  │
│ [해결책] 역할 분담!                                               │
│ • YOLO: normal/worn 분류 (마모 여부 1차 판단)                     │
│ • LLM: 마모도(%) + 위험 상태(crack/flat/bulge/uneven) 전부 담당   │
└─────────────────────────────────────────────────────────────────┘

[재학습 계획]
1. LLM이 측정한 마모도 + 위험상태 데이터가 S3에 축적됨
2. 데이터가 1000장 이상 쌓이면:
   - Tire YOLO 다중클래스 재학습 (crack/flat/bulge/uneven 추가)
   - Regression 모델 학습 (마모도 % 직접 예측)

[API 응답 형식]
{
  "status": "WARNING",
  "analysis_type": "SCENE_TIRE",
  "category": "TIRE",
  "data": {
    "wear_status": "GOOD",     // GOOD(양호), DANGER(위험)
    "wear_level_pct": 45,      // 마모도 %
    "critical_issues": ["cracked"],  // LLM이 감지한 위험 상태
    "description": "...",
    "recommendation": "...",
    "is_replacement_needed": false
  }
}
"""
import os
from typing import List, Union, Dict, Any
from PIL import Image
from ai.app.services.router_service import CONFIDENCE_THRESHOLD

# =============================================================================
# Reliability Thresholds
# =============================================================================
FAST_PATH_THRESHOLD = 0.9  # 이 값 이상이면 LLM 없이 로컬 결과 반환 (테스트용)


async def run_tire_yolo(
    image: Union[str, Image.Image], 
    yolo_model
) -> Dict[str, Any]:
    """
    [YOLO 역할] 타이어 마모 여부만 1차 판단
    
    ┌─────────────────────────────────────────────────────────────┐
    │ 현재 데이터셋 한계:                                          │
    │ - normal: 정상 타이어                                        │
    │ - worn: 마모된 타이어                                        │
    │                                                              │
    │ crack, flat, bulge, uneven 등은 데이터셋에 없음!             │
    │ → 이런 세부 위험 상태는 LLM이 감지함                          │
    └─────────────────────────────────────────────────────────────┘
    
    Returns:
        {
            "is_worn": true/false,  # 마모 여부
            "confidence": 0.85,     # 신뢰도
            "label": "worn"         # 감지된 라벨
        }
    """
    if yolo_model is None:
        return {"is_worn": None, "confidence": 0.0, "label": None}
    
    try:
        results = yolo_model.predict(source=image, save=False, conf=0.25)
        
        if not results or len(results) == 0:
            return {"is_worn": None, "confidence": 0.0, "label": None}
            
        r = results[0]
        # Classification 모델은 r.probs를 사용함
        if hasattr(r, 'probs') and r.probs is not None:
            top1_idx = int(r.probs.top1)
            label_name = yolo_model.names[top1_idx].lower()
            confidence = float(r.probs.top1conf)
            
            return {
                "is_worn": label_name == "cracked" or label_name == "worn", # cracked와 worn 모두 이상으로 간주
                "confidence": round(confidence, 2),
                "label": label_name
            }
        
        # 만약 Detection 모델인 경우 (하위 호환성 유지)
        best_detection = None
        max_confidence = 0.0
        if hasattr(r, 'boxes'):
            for box in r.boxes:
                label_idx = int(box.cls[0])
                label_name = yolo_model.names[label_idx].lower()
                confidence = float(box.conf[0])
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_detection = {
                        "is_worn": label_name == "cracked" or label_name == "worn",
                        "confidence": round(confidence, 2),
                        "label": label_name
                    }
        
        return best_detection or {"is_worn": None, "confidence": 0.0, "label": None}
        
    except Exception as e:
        print(f"[Tire YOLO Error] {e}")
        return {"is_worn": None, "confidence": 0.0, "label": None}


async def get_tire_analysis_from_llm(s3_url: str) -> Dict[str, Any]:
    """
    [LLM 역할] 마모도(%) + 위험 상태 전부 측정
    
    ┌─────────────────────────────────────────────────────────────┐
    │ LLM이 담당하는 것:                                           │
    │ 1. 마모도 (wear_level_pct): 0~100%                          │
    │ 2. 위험 상태 감지 (critical_issues):                         │
    │    - cracked: 균열이 보이는가?                               │
    │    - flat: 공기가 빠져 보이는가?                             │
    │    - bulge: 측면이 부풀어 올랐는가?                          │
    │    - uneven: 편마모가 있는가?                                │
    │ 3. 상태 판단 및 권고사항                                     │
    └─────────────────────────────────────────────────────────────┘
    
    [반환값]
    {
        "wear_level_pct": 45,
        "wear_status": "GOOD",  // GOOD 또는 DANGER
        "critical_issues": ["cracked"],  // 또는 null
        "description": "...",
        "recommendation": "...",
        "is_replacement_needed": false
    }
    """
    try:
        from ai.app.services.llm_service import call_openai_vision
        
        # =================================================================
        # LLM 프롬프트: 타이어 전문가 역할
        # =================================================================
        PROMPT = """당신은 타이어 전문 기술자입니다. 이 타이어 이미지를 분석하세요.

[분석 항목]
1. 마모도 측정 (0~100%)
   - 트레드 홈의 깊이: 신품 약 8mm, 교체 권장은 1.6mm 이하
   - 마모 한계선(TWI): 홈 사이의 작은 돌기가 보이면 70% 이상 마모

2. 위험 상태 감지 (해당하는 것 모두 선택)
   - cracked: 균열이 보이나요? (표면/측면 균열)
   - flat: 공기가 빠져 보이나요? (찌그러진 형태)
   - bulge: 측면이 부풀어 올랐나요? (즉시 교체 필요!)
   - uneven: 편마모가 있나요? (한쪽만 닳음)

3. 상태 판단
   - GOOD: 정상 (마모도 0~60%, 위험 상태 없음)
   - DANGER: 위험 (마모도 60%+ 또는 위험 상태 발견)

[응답 형식 - 반드시 JSON으로]
{
    "wear_level_pct": 45,
    "wear_status": "GOOD",
    "critical_issues": null,
    "description": "타이어가 45% 마모되었습니다. 트레드 홈이 약 4.5mm 남아있습니다.",
    "recommendation": "현재 상태로 약 10,000km 주행 가능합니다. 5,000km 후 재점검을 권장합니다.",
    "is_replacement_needed": false
}

[critical_issues 예시]
- 위험 없음: null
- 균열만: ["cracked"]
- 여러 개: ["cracked", "uneven"]

[is_replacement_needed 기준]
- true: 마모도 60% 이상 또는 cracked/flat/bulge 발견
- false: 그 외"""

        # LLM 호출
        result = await call_openai_vision(s3_url, PROMPT)
        
        # critical_issues가 빈 배열이면 null로 변환
        if result.get("critical_issues") == []:
            result["critical_issues"] = None
            
        return result
        
    except Exception as e:
        print(f"[Tire LLM Error] {e}")
        # LLM 실패 시 기본값 반환
        return {
            "wear_level_pct": None,
            "wear_status": "UNKNOWN",
            "critical_issues": None,
            "description": "마모도 측정에 실패했습니다.",
            "recommendation": "정비소에서 직접 점검을 권장합니다.",
            "is_replacement_needed": False
        }


async def analyze_tire_image(
    image: Image.Image,
    s3_url: str, 
    yolo_model=None
) -> Dict[str, Any]:
    """
    [메인 함수] 타이어 종합 분석
    
    ┌─────────────────────────────────────────────────────────────┐
    │ 분석 파이프라인                                               │
    │                                                              │
    │ [Step 1] YOLO: 마모 여부 1차 판단 (normal/worn)               │
    │    │       → 데이터셋 한계로 세부 분류 불가                    │
    │    │                                                         │
    │ [Step 2] LLM: 마모도(%) + 위험상태 정밀 측정                   │
    │    │       → crack/flat/bulge/uneven 감지                    │
    │    │       → 마모도 % 정밀 측정                               │
    │    │                                                         │
    │ [Step 3] Active Learning: 분석 데이터 S3 저장                 │
    │           → 미래 YOLO 다중클래스 재학습에 사용                 │
    └─────────────────────────────────────────────────────────────┘
    """
    
    # =================================================================
    # Step 1: YOLO로 마모 여부 1차 판단 (선택적)
    # =================================================================
    # YOLO는 normal/worn만 분류 가능 (데이터셋 한계)
    # 세부 분석은 LLM이 담당하므로 YOLO 결과는 참고용
    yolo_result = None
    if yolo_model is not None:
        yolo_result = await run_tire_yolo(image, yolo_model)
        print(f"[Tire] YOLO 1차 판단: {yolo_result}")
    
    # 신뢰도가 매우 높으면 로컬 결과만으로 리포트 생성 (LLM 비용 절감 및 속도)
    if yolo_result and yolo_result.get("confidence", 0) >= FAST_PATH_THRESHOLD:
        print(f"[Tire] Fast Path 적용 (신뢰도: {yolo_result['confidence']}). LLM 스킵.")
        label = yolo_result.get("label", "normal")
        
        if label == "worn" or label == "cracked":
            wear_status = "DANGER"
            wear_level_pct = 85
            critical_issues = ["crack"] if label == "cracked" else None
            description = "타이어 마모가 심각하거나 균열이 감지되었습니다. 즉시 교체가 필요합니다."
            recommendation = "가까운 정비소에서 즉시 타이어를 교체하십시오."
            is_replacement_needed = True
            final_status = "CRITICAL"
        else:
            wear_status = "GOOD"
            wear_level_pct = 20
            critical_issues = None
            description = "타이어 상태가 양호합니다. 홈의 깊이가 충분하며 마모 한계선과의 거리가 멉니다."
            recommendation = "현재 상태가 양호하므로 정기적인 공기압 보충과 위치 교환을 권장합니다."
            is_replacement_needed = False
            final_status = "NORMAL"
            
        return {
            "status": final_status,
            "analysis_type": "SCENE_TIRE",
            "category": "TIRE",
            "data": {
                "wear_status": wear_status,
                "wear_level_pct": wear_level_pct,
                "critical_issues": critical_issues,
                "description": description,
                "recommendation": recommendation,
                "is_replacement_needed": is_replacement_needed
            }
        }

    # =================================================================
    # Step 2: LLM으로 마모도(%) + 위험상태 정밀 측정 (저신뢰 데이터 등)
    # =================================================================
    print(f"[Tire] LLM 정밀 분석 시작 (신뢰도 낮음)...")
    llm_result = await get_tire_analysis_from_llm(s3_url)
    
    wear_level_pct = llm_result.get("wear_level_pct")
    wear_status = llm_result.get("wear_status", "UNKNOWN")
    critical_issues = llm_result.get("critical_issues")
    description = llm_result.get("description", "")
    recommendation = llm_result.get("recommendation", "")
    is_replacement_needed = llm_result.get("is_replacement_needed", False)
    
    # =================================================================
    # Step 3: 최종 상태 결정
    # =================================================================
    # status는 프론트엔드에서 UI 색상을 결정하는 데 사용
    # - NORMAL: 초록색 (안전)
    # - WARNING: 노란색 (주의)
    # - CRITICAL: 빨간색 (위험)
    
    if wear_status == "DANGER" or is_replacement_needed:
        # 위험 상태 또는 교체 필요
        if critical_issues and any(issue in critical_issues for issue in ["cracked", "flat", "bulge"]):
            # 심각한 위험 상태
            final_status = "CRITICAL"
        elif wear_level_pct and wear_level_pct >= 80:
            final_status = "CRITICAL"
        else:
            final_status = "WARNING"
    elif wear_status == "UNKNOWN":
        final_status = "UNKNOWN"
    else:
        final_status = "NORMAL"
    
    # =================================================================
    # Step 4: Active Learning - 분석 데이터 S3 저장
    # =================================================================
    # 이 데이터가 축적되면:
    # 1. Tire YOLO 다중클래스 재학습 (crack/flat/bulge/uneven 추가)
    # 2. Regression 모델 학습 (마모도 % 직접 예측)
    await _save_tire_analysis_data(s3_url, llm_result, yolo_result)
    
    # =================================================================
    # 응답 반환 (API 명세서 형식)
    # =================================================================
    return {
        "status": final_status,
        "analysis_type": "SCENE_TIRE",
        "category": "TIRE",
        "data": {
            "wear_status": wear_status,
            "wear_level_pct": wear_level_pct,
            "critical_issues": critical_issues,
            "description": description,
            "recommendation": recommendation,
            "is_replacement_needed": is_replacement_needed
        }
    }


async def _save_tire_analysis_data(
    s3_url: str, 
    llm_result: Dict[str, Any],
    yolo_result: Dict[str, Any] = None
):
    """
    [Active Learning] 타이어 분석 데이터를 S3에 저장
    
    ┌─────────────────────────────────────────────────────────────┐
    │ 저장하는 데이터:                                             │
    │ - 마모도 % (LLM 측정값) → Regression 모델 학습용             │
    │ - 위험 상태 (LLM 감지값) → YOLO 다중클래스 재학습용          │
    │ - YOLO 결과 (있으면) → 비교 분석용                           │
    └─────────────────────────────────────────────────────────────┘
    
    [저장 경로]
    dataset/tire/llm_confirmed/{file_id}.json
    """
    try:
        import boto3
        import json
        
        # 품질 필터링: LLM 측정 실패한 경우 저장 안 함
        if llm_result.get("wear_level_pct") is None:
            print("[Active Learning Tire] 배제: 마모도 측정 실패")
            return
        
        if llm_result.get("wear_status") == "UNKNOWN":
            print("[Active Learning Tire] 배제: 상태 불명")
            return
        
        # S3에 저장
        s3 = boto3.client('s3')
        bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
        
        # 파일 ID 추출: s3_url이 base64인 경우 처리
        if s3_url.startswith("data:"):
            import hashlib
            file_id = hashlib.md5(s3_url.encode()).hexdigest()[:10]
        else:
            file_id = os.path.basename(s3_url).split('.')[0]
            
        label_key = f"dataset/llm_confirmed/visual/tire/{file_id}.json"
        
        # 저장할 데이터 구조
        training_data = {
            "source_url": s3_url,
            # 마모도 관련 (Regression 학습용)
            "wear_level_pct": llm_result.get("wear_level_pct"),
            "wear_status": llm_result.get("wear_status"),
            # 위험 상태 관련 (YOLO 다중클래스 재학습용)
            "critical_issues": llm_result.get("critical_issues"),
            # 기타
            "is_replacement_needed": llm_result.get("is_replacement_needed"),
            "labeled_by": "LLM_ORACLE",
            # YOLO 결과 (비교 분석용)
            "yolo_result": yolo_result
        }
        
        s3.put_object(
            Bucket=bucket,
            Key=label_key,
            Body=json.dumps(training_data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        print(f"[Active Learning Tire] 분석 데이터 저장 완료: {label_key}")
        
        # Manifest에도 기록
        from ai.app.services.manifest_service import add_visual_entry
        add_visual_entry(
            original_url=s3_url,
            category="TIRE",
            label_key=label_key,
            status=llm_result.get("wear_status", "UNKNOWN"),
            analysis_type="LLM_TIRE_ANALYSIS",
            detections=None,
            confidence=1.0  # LLM 측정값이므로 신뢰도 100%
        )
        
    except Exception as e:
        # Active Learning 실패해도 메인 분석에는 영향 없음
        print(f"[Active Learning Tire] 저장 실패 (무시): {e}")
