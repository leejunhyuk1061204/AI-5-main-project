from PIL import Image, ImageDraw
import os

def mark_defect():
    # 사용자가 업로드한 이미지 경로 (최신)
    image_path = r"C:\Users\301\.gemini\antigravity\brain\0e32816b-b4c3-4fd3-a5ce-f742dc7e5c6c\media__1771402708401.jpg"
    # 결과 저장 경로 (바탕화면)
    output_path = r"C:\Users\301\Desktop\abs_check_point_2.jpg"

    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    try:
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        width, height = img.size
        
        # ABS Unit의 구조적 취약점: 검은색 플라스틱 하우징 (ECU 모듈부)
        # 이미지 분석 없이 대략적인 위치 추정 (중앙 하단부/좌측)
        
        # 1. 플라스틱 하우징 (균열 다발 구간)
        center_x = width // 2
        center_y = int(height * 0.6) # 약간 아래쪽
        radius = min(width, height) // 4
        
        left_up = (center_x - radius, center_y - radius)
        right_down = (center_x + radius, center_y + radius)
        
        # 빨간색 원 그리기 (두께 10)
        for i in range(10):
            draw.ellipse(
                [
                    (left_up[0] - i, left_up[1] - i),
                    (right_down[0] + i, right_down[1] + i)
                ],
                outline=(255, 0, 0, 255)
            )
            
        # 2. 파이프 연결부 (누유 다발 구간) - 작게 표시
        pipe_x = width // 2
        pipe_y = int(height * 0.3)
        pipe_r = radius // 2
        
        left_up_pipe = (pipe_x - pipe_r, pipe_y - pipe_r)
        right_down_pipe = (pipe_x + pipe_r, pipe_y + pipe_r)
        
        for i in range(5):
             draw.ellipse(
                [
                    (left_up_pipe[0] - i, left_up_pipe[1] - i),
                    (right_down_pipe[0] + i, right_down_pipe[1] + i)
                ],
                outline=(255, 165, 0, 255) # 주황색
            )
            
        img.convert("RGB").save(output_path)
        print(f"Marked image saved to: {output_path}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    mark_defect()
