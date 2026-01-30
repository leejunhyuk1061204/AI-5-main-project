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
from typing import Dict, Any, Optional, List

class ActiveLearningService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ActiveLearningService, cls).__new__(cls)
            # S3 클라이언트 초기화 (Singleton)
            cls._instance.s3 = boto3.client('s3')
            cls._instance.bucket = os.getenv("S3_BUCKET_NAME", "car-sentry-data")
        return cls._instance

    def save_oracle_label(self, s3_url: str, label_data: Dict[str, Any], domain: str, file_suffix: str = "", confidence: float = 0.0) -> str:
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
            # [New] 정규화된 학습용 JSON 생성
            # Policy가 데이터 구조(Schema)를 결정함
            # [New] 정규화된 학습용 JSON 생성
            # Policy가 데이터 구조(Schema)를 결정함
            normalized_data = ActiveLearningPolicy.normalize_for_training(s3_url, label_data, domain, confidence)
            
            # [Guard] 필터링 후 유효한 라벨이 하나도 없으면 저장 포기
            if not normalized_data["labels"]:
                print(f"[Active Learning] 저장 취소: 유효한 라벨 없음 (Policy Filtered)")
                return None

            normalized_data["labeled_by"] = "LLM_ORACLE" # 내부 추적용

            
            # S3 업로드
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json.dumps(normalized_data, ensure_ascii=False, indent=2),
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
            from ai.app.services.common.manifest_service import add_visual_entry, add_audio_entry
            
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
                    domain=domain if domain else category.lower(), # category가 domain 역할 (engine 등)
                    label_key=label_key,
                    collector="LLM_ORACLE" if analysis_type == "LLM_ORACLE" else "YOLO_HIGH_CONF",
                    confidence=confidence,
                    label_grade="SILVER",
                    requires_human_review=True
                )
            print(f"[Manifest] 기록 완료 ({domain}): {s3_url}")
            
        except Exception as e:
            print(f"[Manifest] 기록 실패 (무시): {e}")


# -------------------------------------------------------------
# 5. Active Learning Policy (재학습 데이터 선별 정책)
# -------------------------------------------------------------
class ActiveLearningPolicy:
    """
    어떤 데이터를 재학습용으로 수집할지 결정하는 정책 클래스
    (Router/Filter 패턴)
    """
    
    @staticmethod
    def should_collect(
        status: str, 
        confidence: float, 
        labels: Optional[List] = None, 
        is_llm_fallback: bool = False
    ) -> bool:
        """
        재학습 데이터 수집 여부 판단
        
        Args:
            status: 차량 상태 (NORMAL, WARNING, CRITICAL, ERROR)
            confidence: 모델/라우터 신뢰도
            labels: 감지된 객체 리스트
            is_llm_fallback: LLM이 생성한 데이터인지 여부
            
        Returns:
            True: 수집 대상
            False: 수집 제외
        """
        # 1. [Filter] 에러 상태는 수집 안함
        if status in ["ERROR", "FAILED", "UNKNOWN"]:
            return False
            
        # 2. [Case] LLM Fallback 데이터 (Oracle)
        # LLM이 "확실히 문제가 있다(WARNING/CRITICAL)"고 하고, 라벨도 만들어줬으면 수집 가치 높음
        if is_llm_fallback:
            if status in ["WARNING", "CRITICAL"] and labels and len(labels) > 0:
                return True
            return False
            
        # 3. [Case] YOLO Native 데이터 (Confidence 기반)
        # 너무 확실한 것(>0.9)은 배울게 적고, 너무 불확실한 것(<0.4)은 노이즈일 수 있음.
        # "애매한" 구간(0.4 ~ 0.85) 집중 수집
        if 0.4 <= confidence < 0.85:
            # 특히 뭔가 발견했는데(WARNING) 확신이 부족할 때
            if status in ["WARNING", "CRITICAL"]:
                return True
                
        return False

    @staticmethod
    def estimate_quality(bbox: list) -> float:
        """
        [Heuristic] BBox 품질 추정 (Confidence Score)
        - 너무 작으면 불확실(0.4), 적당하면 보통(0.6), 크면 확실(0.7)
        - LLM Oracle 상한선은 0.7로 제한 (Human=1.0)
        """
        if not bbox or len(bbox) != 4:
            return 0.0
        
        w, h = bbox[2], bbox[3]
        area = w * h
        
        if area < 0.01: # 1% 미만 (매우 작음)
            return 0.4
        if area < 0.1:  # 10% 미만 (보통)
            return 0.6
        return 0.7     # 큼 (확실)

    @staticmethod
    def normalize_for_training(s3_url: str, llm_labels: dict, domain: str, confidence: float = 0.0) -> dict:
        """
        [Policy] LLM 출력 결과 → Rich Label Schema (Weak Label v2)
        """
        annotations = []
        raw_labels = llm_labels.get("labels", [])
        
        for lbl in raw_labels:
            bbox = lbl.get("bbox", [0, 0, 0, 0])
             
            # [Safety Net] Hard Rule Filter
            if len(bbox) != 4: continue
            area = bbox[2] * bbox[3]
            if area > 0.7 or area < 0.001: continue
            if not (0.0 <= bbox[0] <= 1.0): continue

            # Quality 추정
            quality_score = ActiveLearningPolicy.estimate_quality(bbox)

            annotations.append({
                "class": lbl.get("class", "Unknown"),
                "bbox": bbox,
                "label_source": "LLM_ORACLE",
                "label_quality": quality_score,
                "verification": {
                    "status": "UNVERIFIED",
                    "verified_by": None,
                    "verified_at": None
                }
            })
            
        return {
            "schema_version": "al_v2",
            "asset": {
                "type": "image",
                "url": s3_url
            },
            "domain": domain,
            "labels": annotations,
            "collection_context": {
                "trigger": "LOW_CONFIDENCE",
                "analysis_type": "LLM_FALLBACK",
                "model_confidence": confidence
            },
            "timestamps": {
                "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
        }


# 전역 인스턴스 접근 함수
def get_active_learning_service():
    return ActiveLearningService()

def get_active_learning_policy():
    return ActiveLearningPolicy()
