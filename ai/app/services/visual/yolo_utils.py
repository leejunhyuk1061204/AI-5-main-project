# ai/app/services/yolo_utils.py
from typing import List

def normalize_bbox(bbox: List[float], width: int, height: int) -> List[int]:
    """
    BBox를 Pixel 좌표로 안전하게 변환합니다.
    - 비율(Ratio, 0.0~1.0) 좌표와 픽셀(Pixel) 좌표 모두를 지원합니다.
    """
    if not bbox or len(bbox) != 4:
        return [0, 0, 0, 0]
    
    # 1. 비율(Ratio) 기반인지 확인 (모든 값이 0.0~1.0 사이인 경우)
    if all(0.0 <= float(v) <= 1.0 for v in bbox):
        x1 = int(bbox[0] * width)
        y1 = int(bbox[1] * height)
        x2 = int(bbox[2] * width)
        y2 = int(bbox[3] * height)

        # 만약 x2, y2가 너비/높이가 아니라 좌표인 경우를 대비해 보정
        # (YOLO의 xywh vs xyxy 차이 방어)
        if x2 < x1 or y2 < y1:
            x2 = x1 + int(bbox[2] * width)
            y2 = y1 + int(bbox[3] * height)

        return [x1, y1, x2, y2]
    
    # 2. 이미 픽셀 기반인 경우 정수형으로 변환하여 반환
    return [int(v) for v in bbox]


def convert_xywh_to_xyxy(x, y, w, h):
    """
    Center-WH -> Corner-XY
    """
    x1 = int(x - w / 2)
    y1 = int(y - h / 2)
    x2 = int(x + w / 2)
    y2 = int(y + h / 2)
    return [x1, y1, x2, y2]


def normalize_to_xywh(bbox: List[float], width: int, height: int) -> List[int]:
    """
    BBox를 [x, y, w, h] Pixel 좌표로 변환합니다. (x, y는 좌측 상단)
    - 비율(Ratio) 및 픽셀(Pixel) 입력 모두 지원
    """
    xyxy = normalize_bbox(bbox, width, height)
    x1, y1, x2, y2 = xyxy
    return [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]


def normalize_label(label: str) -> str:
    """
    라벨 이름을 일관된 형식으로 정규화합니다.
    - 소문자 변환
    - 공백 및 하이픈을 언더스코어로 변환
    """
    if not label:
        return "unknown"
    return label.lower().strip().replace(" ", "_").replace("-", "_")
