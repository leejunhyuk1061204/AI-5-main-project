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
