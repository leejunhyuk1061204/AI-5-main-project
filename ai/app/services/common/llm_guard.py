from typing import Dict, Any, List, Optional

def validate_llm_label_result(result: Optional[Dict[str, Any]]) -> bool:
    """
    generate_training_labels 결과가 유효한지 검증하는 Guard 함수
    
    Args:
        result: LLM 응답 Dict (generate_training_labels 반환값)
        
    Result:
        True: 유효함 (labels를 사용해도 됨)
        False: 유효하지 않음 (FAILED, EMPTY, Error 등)
    """
    # 1. None 체크
    if not result:
        return False
        
    # 2. Status 체크
    # "FAILED"나 "ERROR"가 명시되어 있으면 무효
    status = result.get("status", "FAILED")
    if status in ["FAILED", "ERROR"]:
        return False
        
    # 3. Label 형식 체크
    labels = result.get("labels")
    if not isinstance(labels, list):
        return False
        
    # 4. 빈 라벨 허용 여부
    # labels가 비어있어도 "NORMAL" 상태라면 "정상(문제없음)"이라는 유효한 판단일 수 있음.
    # 하지만 "박스를 그려야 하는" 로직 입장에서는 박스가 없으면 의미 없으므로
    # 호출하는 쪽에서 has_detections = len(validate(result)) > 0 로 체크해야 함.
    # 여기서는 "형식적 유효성"만 판단.
    
    return True

def sanitize_confidence(bbox_item: Dict[str, Any], heuristic_conf: float = 0.9) -> Dict[str, Any]:
    """
    LLM이 생성한 BBox에 대해 가상의 Confidence를 부여하거나 출처를 명시
    """
    if "confidence" not in bbox_item:
        bbox_item["confidence"] = heuristic_conf
    
    bbox_item["source"] = "LLM_GENERATED"
    return bbox_item
