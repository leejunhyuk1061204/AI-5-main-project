# ai/app/services/crop_service.py
from PIL import Image, ImageOps
import io
from typing import List, Dict, Tuple
from ai.app.schemas.visual_schema import DetectionItem

def crop_with_margin(
    image: Image.Image,
    bbox: List[int],
    margin_ratio: float = 0.15,
    target_size: Tuple[int, int] = (224, 224)
) -> Image.Image:
    """
    detect된 bounding box를 기준으로 margin을 추가하여 crop하고,
    PatchCore 모델 입력을 위해 정사각 Padding 및 Resize를 수행합니다.
    
    Order:
    1. Crop with margin (부품 잘림 방지)
    2. Pad to Square (비율 왜곡 방지)
    3. Resize to 224x224 (모델 입력 규격 맞춤)
    """
    x_center, y_center, w, h = bbox
    
    # 1. Margin 계산
    margin_x = int(w * margin_ratio)
    margin_y = int(h * margin_ratio)

    # 좌표 계산 (x_center, y_center 기준)
    x1 = max(0, int(x_center - w // 2 - margin_x))
    y1 = max(0, int(y_center - h // 2 - margin_y))
    x2 = min(image.width, int(x_center + w // 2 + margin_x))
    y2 = min(image.height, int(y_center + h // 2 + margin_y))

    cropped_image = image.crop((x1, y1, x2, y2))
    
    # 2. Pad to Square (Aspect Ratio Preservation)
    # 가로, 세로 중 긴 쪽에 맞춰서 짧은 쪽에 검은색(0) 패딩을 추가
    w_crop, h_crop = cropped_image.size
    max_dim = max(w_crop, h_crop)
    
    pad_w = (max_dim - w_crop) // 2
    pad_h = (max_dim - h_crop) // 2
    
    # border=(left, top, right, bottom)
    # 홀수 픽셀 차이 보정
    padding = (
        pad_w, 
        pad_h, 
        max_dim - w_crop - pad_w, 
        max_dim - h_crop - pad_h
    )
    
    padded_image = ImageOps.expand(cropped_image, border=padding, fill=0) # 0 is black
    
    # 3. Resize
    final_image = padded_image.resize(target_size, Image.Resampling.LANCZOS)
    
    return final_image

async def crop_detected_parts(
    image_bytes: bytes,
    detections: List[DetectionItem],
    margin_ratio: float = 0.15
) -> Dict[str, Tuple[Image.Image, List[int]]]:
    """
    YOLO 탐지 결과로 부품별 Crop 이미지를 생성하여 반환합니다.
    Returns: {part_name: (PIL_Image, bbox)}
    """
    image = Image.open(io.BytesIO(image_bytes))
    crops = {}

    for det in detections:
        # crop_with_margin 함수로 안전하게 잘라냄
        # bbox is [x_center, y_center, w, h] from visual_schema
        crop = crop_with_margin(image, det.bbox, margin_ratio)
        
        # 중복된 부품명이 있을 경우를 대비해 index 등을 붙일 수도 있으나, 
        # 현재는 덮어쓰기 방지를 위해 label이 유니크하다고 가정하거나 리스트로 반환해야 함.
        # EngineAnomalyPipeline에서 처리하기 좋게, 여기서는 단순 딕셔너리로 반환하되
        # 동일 부품이 여러 개일 경우를 고려해 "_index" suffix를 붙이는 로직 추가
        
        base_label = det.label
        label = base_label
        counter = 1
        while label in crops:
            label = f"{base_label}_{counter}"
            counter += 1
            
        crops[label] = (crop, det.bbox)

    return crops
