
import cv2
import numpy as np
import os
import random
import shutil
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from pathlib import Path

# 사용자가 요청한 8개 부품 리스트
TARGET_PARTS = [
    "ABS_Unit",
    "Air_Filter_Cover",
    "Battery",
    "Brake_Fluid",
    "Engine_Oil_Fill_Cap",
    "Radiator",
    "Engine_Cover",
    "Windshield_Wiper_Fluid"
]



def create_crack_patch(size=(150, 150)):
    """리얼리스틱 균열 패치 (불규칙한 엣지 + 명암)"""
    patch = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    
    # 시작점과 끝점 랜덤 설정
    margin = min(20, size[0]//4, size[1]//4)
    if margin < 1: margin = 1
    
    # 안전 범위 확보
    max_x = max(margin + 1, size[0] - margin)
    max_y = max(margin + 1, size[1] - margin)
    
    start_x = random.randint(margin, max_x)
    start_y = random.randint(margin, max_y)
    
    points = [(start_x, start_y)]
    curr_x, curr_y = start_x, start_y
    
    # 지그재그 경로 생성
    length = random.randint(5, 12)
    for _ in range(length):
        angle = random.uniform(0, 2 * np.pi)
        step = random.randint(10, 30)
        curr_x += step * np.cos(angle)
        curr_y += step * np.sin(angle)
        curr_x = max(margin, min(size[0]-margin, curr_x))
        curr_y = max(margin, min(size[1]-margin, curr_y))
        points.append((curr_x, curr_y))

    # 1. 그림자 (Crack Shadow - Dark)
    draw.line(points, fill=(10, 10, 10, 220), width=4, joint='curve')
    
    # 2. 본체 (Crack Body - Black)
    # 조금 더 얇게, 약간 어긋나게 그려서 깊이감 표현
    offset_points = [(x + random.randint(-1, 1), y + random.randint(-1, 1)) for x, y in points]
    draw.line(offset_points, fill=(0, 0, 0, 255), width=2, joint='curve')

    return patch.filter(ImageFilter.GaussianBlur(0.8))

def create_corrosion_patch(size=(150, 150)):
    """리얼리스틱 부식 패치 (자연스럽게 퍼지는 가루 질감)"""
    # 노이즈 텍스처 생성
    arr = np.random.randint(0, 255, (size[1], size[0], 4), dtype=np.uint8)
    
    # 색상: 하얀색/푸른색 (배터리 산화)
    arr[..., 0] = 200 + np.random.randint(0, 55, size=(size[1], size[0]))
    arr[..., 1] = 220 + np.random.randint(0, 35, size=(size[1], size[0]))
    arr[..., 2] = 255
    
    # 마스크: 중앙에서 불규칙하게 퍼짐
    center_x, center_y = size[0]//2, size[1]//2
    y, x = np.ogrid[:size[1], :size[0]]
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    radius = min(size[0], size[1]) // 3
    
    # Perlin Noise 대용: 거리 기반 + 랜덤
    mask = (dist < radius).astype(float) * 255
    mask *= np.random.uniform(0.5, 1.0, mask.shape) # 구멍 숭숭
    mask = np.clip(mask, 0, 255).astype(np.uint8)
    
    # 외곽 부드럽게
    mask_img = Image.fromarray(mask).filter(ImageFilter.GaussianBlur(8))
    arr[..., 3] = np.array(mask_img)
    
    return Image.fromarray(arr)

def create_stain_patch(size=(150, 150), color='brown'):
    """리얼리스틱 액체 누수 (중앙은 진하고 가장자리는 스며듦)"""
    patch = Image.new('RGBA', size, (0, 0, 0, 0))
    
    # 색상 정의
    if color == 'brown': c_rgb = (80, 40, 0)
    elif color == 'green': c_rgb = (0, 100, 0)
    elif color == 'pink': c_rgb = (200, 20, 80)
    else: c_rgb = (0, 0, 180)
    
    # 그라데이션 원 그리기
    center_x, center_y = size[0]//2, size[1]//2
    max_radius = min(size[0], size[1]) // 2.5
    
    # 여러 겹의 원을 그려 그라데이션 효과 (Alpha Blending)
    draw = ImageDraw.Draw(patch)
    for r in range(int(max_radius), 0, -2):
        alpha = int(200 * (1 - r/max_radius)) # 가장자리는 투명, 중심은 불투명? No, 반대
        # 중심이 진해야 함: r이 작을수록(중심) 진하게 누적
        # 하지만 PIL draw는 덮어쓰기. 큰거부터 그리고 작은거 그리기.
        
        # 방식 변경: Radial Gradient Mask 생성 직접 계산
        pass

    # 직접 픽셀 조작으로 Radial Gradient 구현
    y, x = np.ogrid[:size[1], :size[0]]
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    
    # 불규칙성을 위해 노이즈 추가
    distortion = np.random.uniform(0.9, 1.1, dist.shape)
    dist = dist * distortion
    
    # Alpha: 중심(0) -> 230, 가장자리(max_radius) -> 0
    alpha = np.clip(255 - (dist / max_radius * 255), 0, 230)
    alpha[dist > max_radius] = 0
    
    arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    arr[..., 0] = c_rgb[0]
    arr[..., 1] = c_rgb[1]
    arr[..., 2] = c_rgb[2]
    arr[..., 3] = alpha.astype(np.uint8)
    
    return Image.fromarray(arr)


def create_scratch_patch(size=(150, 150)):
    """리얼리스틱 스크래치 (가늘고 날카로운 선 + 주변 손상)"""
    patch = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    
    # 안전 마진 확보
    margin = min(20, size[0]//4, size[1]//4)
    if margin < 1: margin = 1
    
    max_x = max(margin + 1, size[0] - margin)
    max_y = max(margin + 1, size[1] - margin)
    
    for _ in range(random.randint(2, 4)):
        x1 = random.randint(margin, max_x)
        y1 = random.randint(margin, max_y)
        
        # 길이 제한 (이미지 크기 초과 방지)
        len_x = random.randint(-40, 40)
        len_y = random.randint(-40, 40)
        
        # 좌표 클리핑
        x2 = max(0, min(size[0], x1 + len_x))
        y2 = max(0, min(size[1], y1 + len_y))
        
        # 메인 스크래치 (White, Sharp)
        draw.line([(x1, y1), (x2, y2)], fill=(220, 220, 220, 200), width=1)
        
        # 주변부 잔기스
        for _ in range(3):
            ox1 = max(0, min(size[0], x1 + random.randint(-2, 2)))
            oy1 = max(0, min(size[1], y1 + random.randint(-2, 2)))
            ox2 = max(0, min(size[0], x2 + random.randint(-2, 2)))
            oy2 = max(0, min(size[1], y2 + random.randint(-2, 2)))
            draw.line([(ox1, oy1), (ox2, oy2)], fill=(200, 200, 200, 100), width=1)
            
    return patch

def create_gap_patch(size=(150, 150)):
    """리얼리스틱 유격 (그림자 Gradient)"""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    w = random.randint(min(10, size[0]), int(size[0]*0.9)) # 너비 동적 조절
    h = random.randint(5, max(6, int(size[1]*0.2))) # 높이 동적 조절
    
    x = (size[0] - w) // 2
    y = (size[1] - h) // 2
    
    # 틈의 안쪽 (아주 어두움)
    draw.rectangle([x, y, x+w, y+h], fill=(10, 10, 10, 230))
    
    return img.filter(ImageFilter.GaussianBlur(2))

def create_sludge_patch(size=(120, 120)):
    """오일 슬러지 (덩어리진 텍스처)"""
    return create_stain_patch(size, color='brown')

def create_hole_patch(size=(100, 100)):
    """리얼리스틱 구멍 (내부 그림자 포함)"""
    patch = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    
    margin = 5
    # 크기가 너무 작으면 마진 없이
    if size[0] <= 10 or size[1] <= 10:
        bbox = [0, 0, size[0], size[1]]
    else:
        bbox = [margin, margin, size[0]-margin, size[1]-margin]
        
    try:
        draw.ellipse(bbox, fill=(5, 5, 5, 255))
    except ValueError:
        draw.ellipse([0, 0, size[0], size[1]], fill=(5, 5, 5, 255))
        
    return patch.filter(ImageFilter.GaussianBlur(1))




def apply_augmentation(img):
    """이미지 데이터 증강 (회전, 대칭, 밝기, 대비)"""
    # 1. 랜덤 회전 (-10 ~ 10도)
    if random.random() > 0.3:
        angle = random.randint(-10, 10)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False)
        
    # 2. 좌우 반전
    if random.random() > 0.5:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        
    # 3. 밝기 조절 (0.8 ~ 1.2)
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(random.uniform(0.8, 1.2))
    
    # 4. 대비 조절 (0.8 ~ 1.2)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(random.uniform(0.8, 1.2))
    
    return img

def main():
    # 소스 1: 대량 원본 (Priority 1)
    base_data_path_1 = Path(r"C:\Users\301\Desktop\data\anomaly")
    # 소스 2 & 타겟: bad/bad 폴더 (Priority 2 & Output)
    base_data_path_2 = Path(r"C:\Users\301\Desktop\bad\bad")
    output_base_path = Path(r"C:\Users\301\Desktop\bad\bad")
    
    # 1. 불필요한 폴더 삭제 (TARGET_PARTS 제외)
    if output_base_path.exists():
        for item in output_base_path.iterdir():
            if item.is_dir() and item.name not in TARGET_PARTS:
                print(f"Removing unused folder: {item.name}")
                shutil.rmtree(item)

    # 2. 타겟 부품에 대해서만 데이터 생성
    for part in TARGET_PARTS:
        print(f"Processing {part}...")
        
        # 소스 이미지 수집
        images = []
        is_source_abundant = False
        
        # 1순위: data/anomaly 검색
        source_dir_1 = base_data_path_1 / part
        if source_dir_1.exists():
            images = list(source_dir_1.rglob("*good/*.jpg")) + list(source_dir_1.rglob("*good/*.png"))
            if not images: # good 없으면 전체
                 images = list(source_dir_1.glob("*.jpg")) + list(source_dir_1.glob("*.png"))
        
        if len(images) > 30:
            is_source_abundant = True
            print(f"  - Use abundant source from data/anomaly ({len(images)} images)")
        else:
            # 2순위: bad/bad 내의 '*defect*' 파일 검색 (기존 원본으로 추정)
            source_dir_2 = base_data_path_2 / part
            if source_dir_2.exists():
                # _abnormal_은 생성된 것이므로 제외하고 순수 defect 파일만
                detected = list(source_dir_2.glob("*defect*.jpg")) + list(source_dir_2.glob("*defect*.png"))
                # 혹시 defect 패턴이 없으면, abnormal이 아닌 모든 파일 사용
                if not detected:
                     all_imgs = list(source_dir_2.glob("*.jpg")) + list(source_dir_2.glob("*.png"))
                     detected = [f for f in all_imgs if "_abnormal_" not in f.name]
                
                images = detected
                print(f"  - Use limited source from bad/bad ({len(images)} images) with Augmentation)")

        target_dir = output_base_path / part
        target_dir.mkdir(parents=True, exist_ok=True)
        
        if not images:
            print(f"Warning: No images found for {part} in either paths")
            continue
            
        # 50장 생성
        total_to_generate = 50
        for i in range(total_to_generate):
            try:
                # 랜덤 복원 추출
                src_img_path = random.choice(images)
                img = Image.open(src_img_path).convert('RGBA')
            except Exception as e:
                print(f"Skipping image due to error: {e}")
                continue
                
            # 원본이 부족하면 증강(Augmentation) 적용하여 중복 회피
            if not is_source_abundant:
                img = apply_augmentation(img)
            
            # 결함 합성 적용
            width, height = img.size
            d_w, d_h = max(50, width // 2), max(50, height // 2)
            defect = None
            
            if part == 'Battery':
                if random.random() > 0.5: defect = create_corrosion_patch((d_w, d_h))
                else: defect = create_sludge_patch((d_w, d_h))
            elif part == 'Windshield_Wiper_Fluid':
                if random.random() > 0.4: defect = create_stain_patch((d_w, int(height*0.8)), color='blue')
                else: defect = create_crack_patch((width, height))
            elif part == 'Engine_Oil_Fill_Cap':
                if random.random() > 0.5: defect = create_sludge_patch((d_w, d_h))
                else: defect = create_hole_patch((d_w, d_h))
            elif part == 'Brake_Fluid':
                if random.random() > 0.5: defect = create_stain_patch((d_w, int(height*0.6)), color='brown')
                else: defect = create_crack_patch((width, height))
            elif part == 'Radiator':
                color = 'green' if random.random() > 0.5 else 'pink'
                defect = create_stain_patch((d_w, d_h), color=color)
            elif part == 'Engine_Cover':
                defect = create_scratch_patch((width, height))
            elif part == 'Air_Filter_Cover':
                defect = create_gap_patch((width, height))
            else:
                defect = create_crack_patch((width, height))
                
            if defect:
                pos_x = (width - defect.size[0]) // 2 + random.randint(-20, 20)
                pos_y = (height - defect.size[1]) // 2 + random.randint(-20, 20)
                img.alpha_composite(defect, (pos_x, pos_y))
            
            out_name = f"{part}_abnormal_v6_{i+1}.jpg"
            img.convert('RGB').save(target_dir / out_name, "JPEG", quality=95)
            
    print("Done! Only target parts processed. Unused folders removed.")

if __name__ == "__main__":
    main()
