# ai/scripts/sync_active_learning.py
"""
LLM 티처 기반 Active Learning 데이터 동기화 도구 (Active Learning Synchronizer)

[역할]
1. LLM 교정 데이터 수집: ML 모델이 틀렸거나 모호했던 사례(Confidence < 0.9) 중, LLM(Teacher)이 정답을 판별하여 S3에 저장한 고품질 데이터(Image + JSON)를 다운로드합니다.
2. 학습셋 자동 변환: LLM이 내린 정답(JSON)을 YOLO 표준 포맷(.txt)으로 자동 변환합니다.
3. 데이터셋 병합: 변환된 데이터와 이미지를 로컬 `ai/data/[domain]/train` 디렉토리에 자동으로 주입합니다.

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
    "tire": ["normal", "cracked", "worn", "flat", "bulge"],
    "engine": ["Battery", "Engine_Cover", "Oil_Cap", "Coolant_Reservoir", "Fuse_Box"], # 예시
    "exterior": ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"],
    "audio": ["ENG_IDLE", "ENG_KNOCKING", "BRAKE_SQUEAL", "SUSP_CLUNK"] # AST용 예시
}

async def download_file(s3_url, target_path):
    """S3 URL에서 파일을 다운로드하여 로컬에 저장"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(s3_url)
            response.raise_for_status()
            with open(target_path, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"      [Error] 파일 다운로드 실패: {e}")
            return False

async def sync_data(domain, limit):
    print(f"\n[Active Learning] {domain.upper()} 도메인 데이터 동기화 시작 (최대 {limit}개)...")
    
    # 1. S3 연결
    s3 = boto3.client('s3')
    bucket_name = S3_BUCKET
    
    # 2. S3의 'dataset/{domain}/llm_confirmed/' 경로 탐색
    prefix = f"dataset/{domain}/llm_confirmed/"
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    except Exception as e:
        print(f"[Error] S3 접근 실패: {e}")
        return

    if 'Contents' not in response:
        print("[Info] 새로운 정답지(JSON)가 없습니다.")
        return

    json_files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.json')]
    print(f"[Info] {len(json_files)}개의 정답지를 발견했습니다.")

    # 3. 로컬 디렉토리 준비
    target_data_dir = BASE_DIR / "data" / domain / "train"
    if domain == "audio":
        target_wav_dir = target_data_dir / "wavs"
        target_wav_dir.mkdir(parents=True, exist_ok=True)
        label_file = target_data_dir / "labels.csv" # AST는 보통 CSV나 일괄 라벨 파일 사용
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
        obj = s3.get_object(Bucket=bucket_name, Key=key)
        data = json.loads(obj['Body'].read().decode('utf-8'))
        
        # 원본 파일 URL 찾기
        source_url = data.get("source_url") or f"https://{S3_BUCKET}.s3.ap-northeast-2.amazonaws.com/dataset/{domain}/samples/{file_id}.{'wav' if domain=='audio' else 'jpg'}"

        # 파일 다운로드 (이미지 또는 오디오)
        ext = 'wav' if domain == 'audio' else 'jpg'
        sub_dir = 'wavs' if domain == 'audio' else 'images'
        file_path = target_data_dir / sub_dir / f"{file_id}.{ext}"
        
        if not file_path.exists():
            if not await download_file(source_url, file_path):
                continue

        # 라벨 저장 (YOLO vs AST)
        if domain == "audio":
            label = data.get("label", "NORMAL")
            if label not in class_list:
                new_classes_found.add(label)
            with open(label_file, "a") as f:
                f.write(f"{file_id}.wav,{label}\n")
        else:
            # YOLO txt 포맷 생성
            labels = data.get("labels", [])
            yolo_lines = []
            for lbl in labels:
                cls_name = lbl.get("class")
                if cls_name in class_list:
                    cls_id = class_list.index(cls_name)
                else:
                    # [Dynamic Discovery] 기존에 없던 새로운 부품 발견!
                    new_classes_found.add(cls_name)
                    # 모델이 아직 모르므로 임시로 '99' (Unknown) 처리하거나 스킵
                    # 여기서는 나중에 수동 검수를 위해 0번(임시) 대신 클래스명을 주석으로 남길 수 없으므로 로그만 남김
                    continue # 학습셋 오염 방지를 위해 아직 모르는 클래스는 이미지/라벨만 받고 txt에는 안 적음
                
                bbox = lbl.get("bbox", [0.5, 0.5, 0.1, 0.1])
                yolo_lines.append(f"{cls_id} {' '.join(map(str, bbox))}")

            if yolo_lines:
                with open(target_lbl_dir / f"{file_id}.txt", "w") as f:
                    f.write("\n".join(yolo_lines))
        
        print(f"  - [✓] {file_id} 동기화 완료")
        success_count += 1

    print(f"\n[✓] 총 {success_count}개의 데이터가 학습셋에 성공적으로 병합되었습니다.")
    
    # 신규 클래스 보고
    if new_classes_found:
        print("\n" + "!"*50)
        print("[🚨 New Classes Discovered by LLM Oracle]")
        print(f"다음 부품들은 현재 ML 모델({domain})의 학습 대상에 없습니다:")
        for nc in new_classes_found:
            print(f"  - {nc}")
        print("\n[Action] 위 부품들을 학습시키려면 'data.yaml'과 'DOMAIN_CLASSES'에 추가 후 재학습하세요.")
        print("!"*50)
    
    print(f"\n[✓] 이제 모델을 재학습하여 성능을 강화하세요.")

if __name__ == "__main__":
    import asyncio
    parser = argparse.ArgumentParser(description="LLM-Guided Active Learning Sync")
    parser.add_argument("--domain", type=str, required=True, 
                        choices=["engine", "dashboard", "tire", "exterior", "audio"])
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    
    asyncio.run(sync_data(args.domain, args.limit))
