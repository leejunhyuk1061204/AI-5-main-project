# app/services/visual_service.py
from ai.app.services.llm_service import analyze_general_image
from ai.app.services.yolo_service import run_yolo_inference # YOLO 실행 로직 분리 가정

async def get_smart_visual_diagnosis(s3_url: str, yolo_model=None):
    # 1. 우선 YOLO(best.pt)에게 계기판인지 물어봅니다.
    yolo_result = await run_yolo_inference(s3_url, model=yolo_model)
    
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
         
         # =========================================================
         # [Data Collection] S3 Abstraction
         # =========================================================
         import boto3
         import uuid
         from datetime import datetime
         import requests
         import os
         
         # 1. 환경 변수 로드
         BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
         
         
         # 2. 공통 변수 설정
         if final_response["type"] == "DASHBOARD":
             category = "DASHBOARD"
         else:
             try:
                 category = getattr(result_content, 'category', 'UNKNOWN')
             except:
                 category = "UNKNOWN"
             
         unique_id = str(uuid.uuid4())[:8]
         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
         filename = f"{timestamp}_{unique_id}.jpg"
         
         try:
             # 이미지 데이터 다운로드 (s3_url은 프론트에서 올라온 임시 URL 등)
             resp = requests.get(s3_url, timeout=5)
             resp.raise_for_status()
             image_data = resp.content
             
             # S3 저장 (STORAGE_TYPE=s3)
             s3_client = boto3.client('s3')
             s3_key = f"dataset/visual/{category}/{filename}"
                 
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
                 
             if final_response["type"] == "DASHBOARD" and result_content.detections:
                try:
                    from PIL import Image
                    import io
                         
                    image = Image.open(io.BytesIO(image_data))
                    img_w, img_h = image.size
                         
                    label_content = ""
                    for det in result_content.detections:
                        if det.class_id is not None:
                            x_c = det.bbox[0] / img_w
                            y_c = det.bbox[1] / img_h
                            w = det.bbox[2] / img_w
                            h = det.bbox[3] / img_h
                            label_content += f"{det.class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}\n"
                         
                    if label_content:
                        label_key = s3_key.replace(".jpg", ".txt")
                        s3_client.put_object(
                            Bucket=BUCKET_NAME,
                            Key=label_key,
                            Body=label_content,
                            Metadata={"related_image": s3_key}
                        )
                        print(f"[YOLO Label] 라벨 저장 완료: s3://{BUCKET_NAME}/{label_key}")
                             
                except Exception as e:
                    print(f"[Warning] S3 라벨 생성 실패: {e}")
                         
         except Exception as e:
             print(f"[Error] 데이터 수집 중 오류: {e}")

    else:
         print("[Data Collection] 품질 미달로 수집 제외.")

    return final_response