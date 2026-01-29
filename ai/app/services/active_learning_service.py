# ai/app/services/active_learning_service.py
"""
Active Learning 데이터 수집 서비스

[역할]
각 도메인 서비스(Visual, Audio, Tire, Engine 등)에서 발생하는 
'저신뢰 데이터'나 'LLM 오라클 데이터'를 중앙 집중적으로 수집하여 S3에 저장합니다.

[기능]
1. 정답 라벨(Oracle) JSON 저장
2. Manifest 파일 업데이트
3. S3 클라이언트 재사용 관리
"""
import os
import json
import boto3
import time
from typing import Dict, Any, Optional

class ActiveLearningService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActiveLearningService, cls).__new__(cls)
            # S3 클라이언트 초기화 (Singleton)
            cls._instance.s3 = boto3.client('s3')
            cls._instance.bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
        return cls._instance

    def save_oracle_label(self, s3_url: str, label_data: Dict[str, Any], domain: str, file_suffix: str = "") -> str:
        """
        LLM이 생성한 정답 라벨(Oracle)을 S3에 저장
        
        Args:
            s3_url: 원본 데이터 S3 URL (파일명 추출용)
            label_data: 저장할 라벨 데이터 (JSON 호환)
            domain: 데이터 도메인 (engine, dashboard, tire, exterior, audio)
            file_suffix: 파일명 뒤에 붙일 식별자 (예: _Battery)
            
        Returns:
            저장된 S3 Key
        """
        try:
            # 파일 ID 추출
            if s3_url.startswith("data:"):
                import hashlib
                file_id = hashlib.md5(s3_url.encode()).hexdigest()[:10]
            else:
                file_id = os.path.basename(s3_url).split('.')[0]
            
            # 저장 경로 생성
            # 예: dataset/llm_confirmed/visual/engine/abc123_Battery.json
            prefix = "audio" if domain == "audio" else f"visual/{domain}"

            suffix = f"_{file_suffix}" if file_suffix else f"_{int(time.time())}"
            key = f"dataset/llm_confirmed/{prefix}/{file_id}{suffix}.json"
            
            # 메타데이터 추가
            if "source_url" not in label_data:
                label_data["source_url"] = s3_url
            label_data["labeled_by"] = "LLM_ORACLE"
            
            # S3 업로드
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(label_data, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
            print(f"[Active Learning] 정답지 저장 완료: {key}")
            return key
            
        except Exception as e:
            print(f"[Active Learning] 저장 실패: {e}")
            return None

    def record_manifest(
        self, 
        s3_url: str, 
        category: str, 
        label_key: str, 
        status: str, 
        confidence: float, 
        analysis_type: str = "LLM_ORACLE",
        detections: Optional[Dict] = None,
        domain: str = "visual"  # [New] 명시적 도메인 파라미터 (visual | audio)
    ):
        """
        Manifest 서비스에 데이터 등록 (이력 관리)
        """
        try:
            # 필요한 모듈 지연 로딩 (순환 참조 방지)
            from ai.app.services.manifest_service import add_visual_entry, add_audio_entry
            
            # [Fix] 문자열 추측 대신 명시적 domain 파라미터 사용
            if domain == "audio":
                 add_audio_entry(
                    original_url=s3_url,
                    category=category,
                    diagnosed_label=analysis_type, 
                    status=status,
                    analysis_type=analysis_type,
                    confidence=confidence
                )
            else:
                add_visual_entry(
                    original_url=s3_url,
                    category=category,
                    label_key=label_key,
                    status=status,
                    analysis_type=analysis_type,
                    detections=detections,
                    confidence=confidence
                )
            print(f"[Manifest] 기록 완료 ({domain}): {s3_url}")
            
        except Exception as e:
            print(f"[Manifest] 기록 실패 (무시): {e}")

# 전역 인스턴스 접근 함수
def get_active_learning_service():
    return ActiveLearningService()
