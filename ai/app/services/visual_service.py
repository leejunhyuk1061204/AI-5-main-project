# app/services/visual_service.py
from ai.app.services.llm_service import analyze_general_image
from ai.app.services.yolo_service import run_yolo_inference # YOLO 실행 로직 분리 가정

async def get_smart_visual_diagnosis(s3_url: str):
    # 1. 우선 YOLO(best.pt)에게 계기판인지 물어봅니다.
    yolo_result = await run_yolo_inference(s3_url)
    
    # 2. 만약 경고등이 하나라도 발견되었다면(계기판이라면) 바로 반환
    if yolo_result.detected_count > 0:
        final_response = {"type": "DASHBOARD", "content": yolo_result}
    else:
        # 3. 발견된 게 없다면 계기판이 아니라고 판단, LLM에게 분석을 넘깁니다.
        print(f"[Visual Service] No dashboard found for: {s3_url}. Routing to LLM.")
        llm_result = await analyze_general_image(s3_url)
        final_response = {"type": "GENERAL_IMAGE", "content": llm_result}

    # [Active Learning] 데이터 수집 필터링
    # 사진 품질이 나빠서(RE_UPLOAD_REQUIRED) 분석 못한 건 학습용으로 쓰면 안 됨
    result_content = final_response["content"]
    if result_content.status != "RE_UPLOAD_REQUIRED" and result_content.status != "ERROR":
         print(f"[Data Collection] 유효한 시각 데이터 수집됨! (Status: {result_content.status})")
         
         import boto3
         import uuid
         from datetime import datetime
         
         s3_client = boto3.client('s3')
         BUCKET_NAME = "your-bucket-name"  # 중요! TODO: 실제 버킷 이름으로 변경 ###
         
         # 카테고리별 폴더 구조: dataset/visual/{CATEGORY}/{filename}.jpg
         # DASHBOARD인 경우 경고등 라벨 사용, 일반 이미지는 LLM이 분류한 카테고리 사용
         if final_response["type"] == "DASHBOARD":
             category = "DASHBOARD"
         else:
             category = getattr(result_content, 'category', 'UNKNOWN')
         
         unique_id = str(uuid.uuid4())[:8]
         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
         s3_key = f"dataset/visual/{category}/{timestamp}_{unique_id}.jpg"
         
         # 원본 파일 다운로드 후 S3에 재업로드 (카테고리 폴더로 이동)
         import requests
         image_data = requests.get(s3_url).content
         s3_client.put_object(
             Bucket=BUCKET_NAME,
             Key=s3_key,
             Body=image_data,
             Metadata={
                 "status": result_content.status,
                 "analysis_type": final_response["type"],
                 "source_url": s3_url
             }
         )
         print(f"[S3 Upload] 저장 완료: s3://{BUCKET_NAME}/{s3_key}")
    else:
         print("[Data Collection] 품질 미달로 수집 제외.")

    return final_response