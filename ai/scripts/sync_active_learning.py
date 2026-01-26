# ai/scripts/sync_active_learning.py
"""
LLM 티처 기반 Active Learning 데이터 동기화 도구 (Active Learning Synchronizer)

[역할]
1. LLM 교정 데이터 수집: ML 모델이 틀렸거나 모호했던 사례(Confidence < 0.9) 중, LLM(Teacher)팀이 정답을 판별하여 S3에 저장한 데이터(Image + JSON)를 다운로드합니다.
2. 학습셋 자동 변환: LLM이 내린 정답(JSON)을 YOLO 표준 포맷(.txt)으로 자동 변환합니다.
3. 데이터셋 병합: 변환된 데이터와 이미지를 로컬 `ai/data/{domain}/retrain` 디렉토리에 자동으로 분류하여 저장합니다.

[사용법]
python ai/scripts/sync_active_learning.py --domain tire --limit 100
"""
import os
import json
import boto3
import argparse
import httpx
from pathlib import Path

# =============================================================================
# [Configuration] 
# =============================================================================
BASE_DIR = Path(__file__).parent.parent  # ai/
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "car-sentry-data")

# 도메인별 클래스 매핑 (실제 모델의 names 리스트와 일치해야 함)
DOMAIN_CLASSES = {
    "dashboard": ["ABS", "Brake", "Battery", "Engine", "ESP", "Overheating", "Oil", "Tire", "Master", "Airbag"],
    "tire": ["normal", "cracked", "worn", "flat", "bulge", "uneven"], # uneven 추가
    "engine": ["Battery", "Engine_Cover", "Oil_Cap", "Coolant_Reservoir", "Fuse_Box"], # 예시
    "exterior": ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"],
    "audio": ["ENG_IDLE", "ENG_KNOCKING", "BRAKE_SQUEAL", "SUSP_CLUNK"] # AST용 예시
}

async def download_file(s3_url, target_path):
    """S3 URL에서 파일을 다운로드하여 로컬에 저장"""
    # boto3를 사용하는 것이 더 안정적임 (인증 문제)
    s3 = boto3.client('s3')
    bucket_name = S3_BUCKET
    
    # s3://bucket/key -> key 추출
    if s3_url.startswith(f"s3://{bucket_name}/"):
        key = s3_url.replace(f"s3://{bucket_name}/", "")
    else:
        # HTTP URL인 경우 (Presigned URL 등)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(s3_url)
                response.raise_for_status()
                with open(target_path, "wb") as f:
                    f.write(response.content)
                return True
            except Exception as e:
                print(f"      [Error] HTTP 다운로드 실패: {e}")
                return False

    try:
        s3.download_file(bucket_name, key, str(target_path))
        return True
    except Exception as e:
        print(f"      [Error] S3 다운로드 실패: {e}")
        return False

async def sync_data(domain, limit):
    print(f"\n[Active Learning] {domain.upper()} 도메인 데이터 동기화 시작 (최대 {limit}개)...")
    
    # 1. S3 연결
    s3 = boto3.client('s3')
    bucket_name = S3_BUCKET
    
    # 2. 사용자 제안 S3 구조에 맞춘 경로 설정
    if domain == "audio":
        prefix = "dataset/llm_confirmed/audio/"
    else:
        prefix = f"dataset/llm_confirmed/visual/{domain}/"
        
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    except Exception as e:
        print(f"[Error] S3 접근 실패: {e}")
        return

    if 'Contents' not in response:
        print(f"[Info] 새로운 정답지(JSON)가 없습니다. (Prefix: {prefix})")
        return

    json_files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.json')]
    print(f"[Info] {len(json_files)}개의 정답지를 발견했습니다.")

    # 3. 로컬 디렉토리 준비
    target_data_dir = BASE_DIR / "data" / domain / "retrain" # retrain 폴더 사용
    if domain == "audio":
        target_wav_dir = target_data_dir / "wavs"
        target_wav_dir.mkdir(parents=True, exist_ok=True)
        label_file = target_data_dir / "labels.csv"
    else:
        target_img_dir = target_data_dir / "images"
        target_lbl_dir = target_data_dir / "labels"
        target_img_dir.mkdir(parents=True, exist_ok=True)
        target_lbl_dir.mkdir(parents=True, exist_ok=True)

    class_list = DOMAIN_CLASSES.get(domain, [])
    success_count = 0
    new_classes_found = set()

    for key in json_files[:limit]:
        file_id = os.path.basename(key).split('.')[0]
        
        # JSON 다운로드
        try:
            obj = s3.get_object(Bucket=bucket_name, Key=key)
            data = json.loads(obj['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"  - [Error] JSON 로드 실패 ({key}): {e}")
            continue
        
        # 원본 파일 URL 찾기
        source_url = data.get("source_url")
        if not source_url:
            print(f"  - [Skip] source_url 정보 없음 ({file_id})")
            continue

        # 파일 다운로드 (이미지 또는 오디오)
        ext = os.path.splitext(source_url)[1] or ('.wav' if domain == 'audio' else '.jpg')
        sub_dir = 'wavs' if domain == 'audio' else 'images'
        file_path = target_data_dir / sub_dir / f"{file_id}{ext}"
        
        if not file_path.exists():
            if not await download_file(source_url, file_path):
                continue

        # 라벨 저장 (YOLO vs AST)
        if domain == "audio":
            label = data.get("label", "NORMAL")
            if label not in class_list:
                new_classes_found.add(label)
            with open(label_file, "a", encoding="utf-8") as f:
                f.write(f"{file_id}{ext},{label}\n")
        else:
            # YOLO txt 포맷 생성
            labels = data.get("labels", [])
            # 타이어 마모도(pct) 학습용 데이터는 별도 처리가 필요할 수 있으나, 일단 YOLO 클래스 학습 위주
            yolo_lines = []
            for lbl in labels:
                cls_name = lbl.get("class")
                if cls_name in class_list:
                    cls_id = class_list.index(cls_name)
                    bbox = lbl.get("bbox", [0.5, 0.5, 0.1, 0.1])
                    yolo_lines.append(f"{cls_id} {' '.join(map(str, bbox))}")
                else:
                    new_classes_found.add(cls_name)
            
            # 타이어 마모도의 경우 critical_issues를 클래스로 활용
            if domain == "tire" and not yolo_lines:
                issues = data.get("critical_issues", [])
                if issues:
                    for issue in issues:
                        if issue in class_list:
                            cls_id = class_list.index(issue)
                            yolo_lines.append(f"{cls_id} 0.5 0.5 0.8 0.8") # 전체 영역 근사

            if yolo_lines:
                with open(target_lbl_dir / f"{file_id}.txt", "w") as f:
                    f.write("\n".join(yolo_lines))
        
        print(f"  - [✓] {file_id} 동기화 및 변환 완료")
        success_count += 1

    print(f"\n[✓] 총 {success_count}개의 데이터가 로컬 'retrain' 폴더에 성공적으로 저장되었습니다.")
    
    if new_classes_found:
        print("\n[🚨 New Classes Discovered]")
        for nc in new_classes_found:
            print(f"  - {nc}")

if __name__ == "__main__":
    import asyncio
    parser = argparse.ArgumentParser(description="LLM-Guided Active Learning Sync")
    parser.add_argument("--domain", type=str, required=True, 
                        choices=["engine", "dashboard", "tire", "exterior", "audio"])
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    
    asyncio.run(sync_data(args.domain, args.limit))
