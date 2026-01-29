# ai/app/services/heatmap_service.py
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import io

def generate_heatmap_overlay(
    original_image: Image.Image,
    heatmap: np.ndarray,
    alpha: float = 0.5,
    colormap: str = "jet"
) -> Image.Image:
    """
    원본 이미지(Crop) 위에 Heatmap을 Overlay하여 시각화합니다.
    
    Args:
        original_image: 원본 PIL 이미지 (Crop된 상태)
        heatmap: Anomaly Score Map (result of PatchCore), shape (H, W) or (224, 224)
        alpha: 투명도 (0.0 ~ 1.0)
    """
    # 1. Heatmap을 원본 이미지 크기로 Resize
    # heatmap은 보통 224x224 정사각이지만, original_image는 직사각일 수 있음 (crop 단계에서 padding 전)
    # 하지만 crop_service에서 패딩 후 224로 리사이즈 했으므로 여기 들어오는 이미지는 224x224임.
    # 만약 원본 비율 crop 위에 덮어씌우려면 역변환이 필요하지만, 
    # LLM에게는 "정사각형 패딩된 버전"을 보여주는 게 왜곡이 없어 더 안전함.
    
    if heatmap.shape[:2] != original_image.size[::-1]:
        # 사이즈가 다르면 heatmap을 이미지 크기로 맞춤
        heatmap_pil = Image.fromarray(heatmap)
        heatmap_pil = heatmap_pil.resize(original_image.size, resample=Image.Resampling.BILINEAR)
        heatmap_resized = np.array(heatmap_pil)
    else:
        heatmap_resized = heatmap

    # 2. Normalize (0~1) - 이미 되어있다고 가정하지만 안전장치
    if heatmap_resized.max() > 0:
        heatmap_normalized = heatmap_resized / heatmap_resized.max()
    else:
        heatmap_normalized = heatmap_resized

    # 3. Apply Colormap
    cmap = plt.get_cmap(colormap)
    # cm.jet returns RGBA (0~1 float) -> RGB (0~255 uint8)
    heatmap_colored = cmap(heatmap_normalized)[:, :, :3] 
    heatmap_colored = (heatmap_colored * 255).astype(np.uint8)
    
    heatmap_img = Image.fromarray(heatmap_colored)

    # 4. Blend
    # Ensure mode matches
    if original_image.mode != 'RGB':
        original_image = original_image.convert('RGB')
        
    overlay = Image.blend(original_image, heatmap_img, alpha=alpha)
    
    return overlay

def heatmap_to_bytes(heatmap_image: Image.Image) -> bytes:
    """Heatmap 이미지를 S3 업로드용 bytes로 변환"""
    buffer = io.BytesIO()
    heatmap_image.save(buffer, format="PNG") # PNG for lossless quality
    buffer.seek(0)
    return buffer.getvalue()
