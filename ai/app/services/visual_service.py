# app/services/visual_service.py
"""
범용 시각 분석 서비스.
- 모든 이미지를 LLM에게 분석 의뢰 (DASHBOARD, EXTERIOR, ENGINE 등 통합)
- 별도의 YOLO 계기판 모델 없이 GPT-4o Vision으로 분류
"""
from ai.app.services.llm_service import analyze_general_image

async def get_smart_visual_diagnosis(s3_url: str, yolo_model=None):
    """
    S3 URL 이미지를 받아 LLM에게 분석을 요청합니다.
    (기존 YOLO 로직 제거 - LLM이 DASHBOARD 포함 모든 카테고리 분류)
    """
    print(f"[Visual Service] Routing to LLM for analysis: {s3_url}")
    
    # LLM에게 범용 분석 요청 (DASHBOARD, EXTERIOR, ENGINE 등 모두 처리)
    llm_result = await analyze_general_image(s3_url)
    final_response = {"type": "LLM_VISION", "content": llm_result}
    
    # =========================================================
    # [Active Learning] Manifest 방식 데이터 수집
    # =========================================================
    result_content = final_response["content"]
    
    # 품질이 나쁜 데이터는 수집 제외
    if result_content.status != "RE_UPLOAD_REQUIRED" and result_content.status != "ERROR":
        print(f"[Data Collection] 유효한 시각 데이터! Manifest에 기록합니다.")
        
        try:
            from ai.app.services.manifest_service import add_visual_entry
            
            category = getattr(result_content, 'category', 'UNKNOWN')
            
            # Manifest에 기록 (이미지 복사 없음!)
            add_visual_entry(
                original_url=s3_url,
                category=category,
                label_key=None,  # YOLO 라벨 삭제됨
                status=result_content.status,
                analysis_type="LLM_VISION",
                detections=None,
                confidence=0.0
            )
            print(f"[Manifest] 원본 위치 기록 완료: {s3_url}")
            
        except Exception as e:
            print(f"[Error] Manifest 기록 실패: {e}")

    else:
        print("[Data Collection] 품질 미달로 수집 제외.")

    return final_response

