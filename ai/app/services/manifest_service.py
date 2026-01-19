# ai/app/services/manifest_service.py
"""
Manifest 기반 Active Learning 데이터 수집 서비스

이미지/오디오 파일을 복사하지 않고, 원본 위치만 기록하여 용량 절약!
"""

import boto3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
VISUAL_MANIFEST_KEY = "dataset/manifest/visual_manifest.json"
AUDIO_MANIFEST_KEY = "dataset/manifest/audio_manifest.json"


def get_s3_client():
    """S3 클라이언트 반환"""
    return boto3.client('s3')


def load_manifest(manifest_key: str) -> Dict[str, Any]:
    """S3에서 manifest.json 로드 (없으면 빈 구조 반환)"""
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=manifest_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except s3.exceptions.NoSuchKey:
        # manifest가 없으면 빈 구조 생성
        return {"training_data": [], "created_at": datetime.now().isoformat()}
    except Exception as e:
        print(f"[Manifest] 로드 실패: {e}")
        return {"training_data": [], "created_at": datetime.now().isoformat()}


def save_manifest(manifest_key: str, manifest_data: Dict[str, Any]) -> bool:
    """manifest.json을 S3에 저장"""
    s3 = get_s3_client()
    try:
        manifest_data["updated_at"] = datetime.now().isoformat()
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=manifest_key,
            Body=json.dumps(manifest_data, ensure_ascii=False, indent=2),
            ContentType='application/json'
        )
        print(f"[Manifest] 저장 완료: s3://{BUCKET_NAME}/{manifest_key}")
        return True
    except Exception as e:
        print(f"[Manifest] 저장 실패: {e}")
        return False


def add_visual_entry(
    original_url: str,
    category: str,
    label_key: Optional[str],
    status: str,
    analysis_type: str,
    detections: Optional[list] = None,
    confidence: float = 0.0
) -> bool:
    """
    시각 데이터 manifest에 항목 추가
    
    Args:
        original_url: 원본 이미지 S3 URL (복사 안 함!)
        category: DASHBOARD, EXTERIOR 등
        label_key: YOLO 라벨 파일 S3 key (있는 경우)
        status: NORMAL, WARNING, CRITICAL 등
        analysis_type: YOLO, LLM_VISION 등
        detections: 탐지된 객체 목록
        confidence: 신뢰도
    """
    manifest = load_manifest(VISUAL_MANIFEST_KEY)
    
    entry = {
        "id": len(manifest["training_data"]) + 1,
        "original_image": original_url,  # 원본 위치만 기록!
        "label": label_key,
        "category": category,
        "status": status,
        "analysis_type": analysis_type,
        "confidence": confidence,
        "detection_count": len(detections) if detections else 0,
        "collected_at": datetime.now().isoformat()
    }
    
    manifest["training_data"].append(entry)
    return save_manifest(VISUAL_MANIFEST_KEY, manifest)


def add_audio_entry(
    original_url: str,
    category: str,
    diagnosed_label: str,
    status: str,
    analysis_type: str,
    confidence: float = 0.0
) -> bool:
    """
    오디오 데이터 manifest에 항목 추가
    
    Args:
        original_url: 원본 오디오 S3 URL (복사 안 함!)
        category: ENGINE, BRAKES, SUSPENSION 등
        diagnosed_label: 진단된 라벨명
        status: NORMAL, FAULTY 등
        analysis_type: AST, LLM_AUDIO 등
        confidence: 신뢰도
    """
    manifest = load_manifest(AUDIO_MANIFEST_KEY)
    
    entry = {
        "id": len(manifest["training_data"]) + 1,
        "original_audio": original_url,  # 원본 위치만 기록!
        "category": category,
        "diagnosed_label": diagnosed_label,
        "status": status,
        "analysis_type": analysis_type,
        "confidence": confidence,
        "collected_at": datetime.now().isoformat()
    }
    
    manifest["training_data"].append(entry)
    return save_manifest(AUDIO_MANIFEST_KEY, manifest)


def get_training_data(manifest_key: str, category: Optional[str] = None) -> list:
    """학습용 데이터 목록 조회"""
    manifest = load_manifest(manifest_key)
    data = manifest.get("training_data", [])
    
    if category:
        data = [d for d in data if d.get("category") == category]
    
    return data
