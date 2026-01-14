# app/services/visual_service.py
from app.services.llm_service import analyze_general_image
from app.services.yolo_service import run_yolo_inference # YOLO 실행 로직 분리 가정

async def get_smart_visual_diagnosis(s3_url: str):
    # 1. 우선 YOLO(best.pt)에게 계기판인지 물어봅니다.
    yolo_result = await run_yolo_inference(s3_url)
    
    # 2. 만약 경고등이 하나라도 발견되었다면(계기판이라면) 바로 반환
    if yolo_result.detected_count > 0:
        return {"type": "DASHBOARD", "content": yolo_result}
    
    # 3. 발견된 게 없다면 계기판이 아니라고 판단, LLM에게 분석을 넘깁니다.
    print(f"[Visual Service] No dashboard found for: {s3_url}. Routing to LLM.")
    llm_result = await analyze_general_image(s3_url)
    
    return {"type": "GENERAL_IMAGE", "content": llm_result}