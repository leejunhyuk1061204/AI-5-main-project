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
    "dashboard": ['Anti Lock Braking System', 'Braking System Issue', 'Charging System Issue', 'Check Engine', 'Electronic Stability Problem -ESP-', 'Engine Overheating Warning Light', 'Low Engine Oil Warning Light', 'Low Tire Pressure Warning Light', 'Master warning light', 'SRS-Airbag'],
    "tire": ["normal", "cracked", "worn", "flat", "bulge", "uneven"], # 미래 확장성(데이터 수집) 고려
    "engine": [
        "Inverter_Coolant_Reservoir", "Battery", "Radiator_Cap", "Windshield_Wiper_Fluid", "Fuse_Box",
        "Power_Steering_Reservoir", "Brake_Fluid", "Engine_Oil_Fill_Cap", "Engine_Oil_Dip_Stick", "Air_Filter_Cover",
        "ABS_Unit", "Alternator", "Engine_Coolant_Reservoir", "Radiator", "Air_Filter", "Engine_Cover",
        "Cold_Air_Intake", "Clutch_Fluid_Reservoir", "Transmission_Oil_Dip_Stick", "Intercooler_Coolant_Reservoir",
        "Oil_Filter_Housing", "ATF_Oil_Reservoir", "Cabin_Air_Filter_Housing", "Secondary_Coolant_Reservoir",
        "Electric_Motor", "Oil_Filter"
    ],
    "exterior": ["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"], # CarDD (파손)
    "audio": ["Normal", "Engine_Knocking", "Engine_Misfire", "Belt_Issue", "Abnormal_Noise", "Brake_Squeal", "Suspension_Clunk", "Exhaust_Leak", "Wheel_Bearing_Hum"] # 서비스 키워드 중심
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

    # [수정] 디렉토리는 실제 파일 저장 직전에 생성하여 빈 폴더 방지
    target_data_dir = BASE_DIR / "data" / domain / "retrain"
    target_img_dir = target_data_dir / "images"
    target_lbl_dir = target_data_dir / "labels"
    target_wav_dir = target_data_dir / "wavs"

    class_list = DOMAIN_CLASSES.get(domain, [])
    success_count = 0
    new_classes_found = set()
    
    # COCO 데이터 구조 (exterior 전용)
    coco_data = {
        "images": [],
        "annotations": [],
        "categories": [{"id": i, "name": name} for i, name in enumerate(class_list)]
    }
    ann_id_counter = 1
    img_id_counter = 1

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
            file_path.parent.mkdir(parents=True, exist_ok=True) # 파일 저장 직전 폴더 생성
            if not await download_file(source_url, file_path):
                continue

        # 라벨 저장 (YOLO vs AST vs COCO vs Classification)
        if domain == "audio":
            label = data.get("label", "NORMAL")
            if label not in class_list:
                new_classes_found.add(label)
            with open(label_file, "a", encoding="utf-8") as f:
                f.write(f"{file_id}{ext},{label}\n")
        elif domain == "exterior":
            # COCO 포맷 데이터 수집 (생략 - 이전과 동일)
            coco_data["images"].append({
                "id": img_id_counter,
                "width": 1024,
                "height": 1024,
                "file_name": f"{file_id}{ext}"
            })
            labels = data.get("labels", [])
            for lbl in labels:
                cls_name = lbl.get("class")
                if cls_name in class_list:
                    cls_id = class_list.index(cls_name)
                    bbox = lbl.get("bbox", [0.5, 0.5, 0.1, 0.1])
                    cw, ch = 1024, 1024
                    x = (bbox[0] - bbox[2]/2) * cw
                    y = (bbox[1] - bbox[3]/2) * ch
                    w = bbox[2] * cw
                    h = bbox[3] * ch
                    coco_data["annotations"].append({
                        "id": ann_id_counter,
                        "image_id": img_id_counter,
                        "category_id": cls_id,
                        "bbox": [x, y, w, h],
                        "area": w * h,
                        "iscrowd": 0
                    })
                    ann_id_counter += 1
                else:
                    new_classes_found.add(cls_name)
            img_id_counter += 1
        elif domain == "tire":
            # 분류(Classification) 모델용: 폴더별 자동 분류
            # LLM이 판단한 critical_issues 중 첫 번째 요소를 클래스로 선택 (없으면 normal)
            issues = data.get("critical_issues", [])
            target_class = "normal"
            if issues:
                # class_list에 있는 것 중 가장 우선순위 높은 것 선택
                for issue in issues:
                    if issue in class_list:
                        target_class = issue
                        break
                if target_class == "normal": # class_list에 없는 새로운 이슈
                    new_classes_found.add(issues[0])
            
            # 이미지를 해당 클래스 폴더로 이동/저장
            class_dir = target_data_dir / target_class
            class_dir.mkdir(parents=True, exist_ok=True)
            
            # 이미 다운로드된 파일을 클래스 폴더로 이동 (또는 처음부터 경로 지정)
            final_file_path = class_dir / f"{file_id}{ext}"
            if file_path.exists() and not final_file_path.exists():
                os.replace(file_path, final_file_path)
            
            print(f"  - [✓] {file_id} ({target_class}) 분류 완료")
        else:
            # YOLO txt 포맷 생성 (Detection 모델용)
            labels = data.get("labels", [])
            yolo_lines = []
            for lbl in labels:
                cls_name = lbl.get("class")
                if cls_name in class_list:
                    cls_id = class_list.index(cls_name)
                    bbox = lbl.get("bbox", [0.5, 0.5, 0.1, 0.1])
                    yolo_lines.append(f"{cls_id} {' '.join(map(str, bbox))}")
                else:
                    new_classes_found.add(cls_name)
            
            if yolo_lines:
                with open(target_lbl_dir / f"{file_id}.txt", "w") as f:
                    f.write("\n".join(yolo_lines))
        
        if domain != "tire": # 타이어는 위에서 별도 출력
            print(f"  - [✓] {file_id} 동기화 완료")
        success_count += 1

    # 외관(exterior) 도메인인 경우 최종 COCO JSON 저장
    if domain == "exterior":
        coco_json_path = target_data_dir / "retrain_coco.json"
        with open(coco_json_path, "w", encoding="utf-8") as f:
            json.dump(coco_data, f, ensure_ascii=False, indent=2)
        print(f"[Info] COCO 통합 장부 저장 완료: {coco_json_path}")

    print(f"\n[✓] 총 {success_count}개의 데이터가 로컬 'retrain' 폴더에 성공적으로 저장되었습니다.")
    
    if new_classes_found:
        print("\n[🚨 New Classes Discovered]")
        for nc in new_classes_found:
            print(f"  - {nc}")

    # 4. 빈 폴더 정리 (실수로 생성된 경우)
    for root, dirs, files in os.walk(target_data_dir, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if not os.listdir(dir_path): # 비어있으면
                os.rmdir(dir_path)

if __name__ == "__main__":
    import asyncio
    parser = argparse.ArgumentParser(description="LLM-Guided Active Learning Sync")
    parser.add_argument("--domain", type=str, required=True, 
                        choices=["engine", "dashboard", "tire", "exterior", "audio"])
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    
    asyncio.run(sync_data(args.domain, args.limit))
