from PIL import Image, ImageDraw
import os

def mark_defect():
    # 사용자가 업로드한 이미지 경로 (최신)
    image_path = r"C:\Users\301\.gemini\antigravity\brain\0e32816b-b4c3-4fd3-a5ce-f742dc7e5c6c\media__1771405242136.jpg"
    # 결과 저장 경로 (바탕화면)
    output_path = r"C:\Users\301\Desktop\engine_cover_check_point.jpg"

    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        width, height = img.size
        
        # 엔진 커버 결함 예상 위치 (스크래치)
        # 1. 좌측 중앙 하단 긴 스크래치
        # (대략적 위치 추정)
        scratch1_center = (int(width * 0.25), int(height * 0.55))
        scratch1_radius = int(width * 0.08)
        
        # 2. 우측 상단 엣지 부분 스크래치
        scratch2_center = (int(width * 0.8), int(height * 0.2))
        scratch2_radius = int(width * 0.06)
        
        # 3. 좌측 상단 작은 스크래치
        scratch3_center = (int(width * 0.3), int(height * 0.3))
        scratch3_radius = int(width * 0.05)
        
        # 빨간색 원 그리기
        centers = [scratch1_center, scratch2_center, scratch3_center]
        radii = [scratch1_radius, scratch2_radius, scratch3_radius]
        
        for center, rad in zip(centers, radii):
            left_up = (center[0] - rad, center[1] - rad)
            right_down = (center[0] + rad, center[1] + rad)
            
            for i in range(8): # 두께
                draw.ellipse(
                    [
                        (left_up[0] - i, left_up[1] - i),
                        (right_down[0] + i, right_down[1] + i)
                    ],
                    outline=(255, 0, 0, 255)
                )

        img.convert("RGB").save(output_path)
        print(f"Marked image saved to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    mark_defect()
