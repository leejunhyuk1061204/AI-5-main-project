from PIL import Image, ImageDraw
import os

def mark_defect():
    # 사용자가 가장 최근에 업로드한 이미지
    image_path = r"C:\Users\301\.gemini\antigravity\brain\0e32816b-b4c3-4fd3-a5ce-f742dc7e5c6c\media__1771396676768.jpg"
    output_path = r"C:\Users\301\.gemini\antigravity\brain\0e32816b-b4c3-4fd3-a5ce-f742dc7e5c6c\abs_defect_highlighted.jpg"

    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        width, height = img.size
        
        # ABS Unit의 검은색 플라스틱 부분 (이미지 하단부) 좌표 추정
        # 사용자가 결함을 묻는 포인트는 주로 '검은색 몸체' 또는 '모서리'
        
        # 원의 크기 및 위치 설정
        circle_radius = min(width, height) // 5
        center_x = width // 2
        center_y = height // 1.5  # 약간 하단 (플라스틱 몸체 쪽)
        
        left_up = (center_x - circle_radius, center_y - circle_radius)
        right_down = (center_x + circle_radius, center_y + circle_radius)
        
        # 빨간색 원 그리기 (두께 8)
        for i in range(8):
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
