import os
import cv2
import base64
from pathlib import Path
from ultralytics import YOLO
from dotenv import load_dotenv
import openai

# .env 파일 로드 (OpenAI API Key 등)
load_dotenv()

# OpenAI API Key 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    print("[Warning] OPENAI_API_KEY not found in .env. LLM fallback will simply return a placeholder.")
    client = None

class HybridDiagnostician:
    def __init__(self, models_root: str):
        self.models_root = Path(models_root)
        self.models = {}
        self.parts = [
            "ABS_Unit", "Air_Filter_Cover", "Battery", "Brake_Fluid", 
            "Engine_Cover", "Engine_Oil_Fill_Cap", "Radiator", "Windshield_Wiper_Fluid"
        ]
        
        print("Loading YOLOv8-cls models...")
        for part in self.parts:
            # 모델 경로: runs/cls/{part}/weights/best.pt
            model_path = self.models_root / part / "weights" / "best.pt"
            if model_path.exists():
                self.models[part] = YOLO(model_path)
                print(f"  [Loaded] {part}")
            else:
                print(f"  [Failed] Model not found for {part} at {model_path}")

    def encode_image(self, image_path):
        """이미지를 base64로 인코딩 (LLM 전송용)"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def ask_llm(self, image_path, part_name, yolo_pred, yolo_conf):
        """LLM (GPT-4o 등)에게 이미지 정밀 분석 요청"""
        if not client:
            return {
                "source": "LLM_FALLBACK (Mock)",
                "status": "Unknown",
                "description": "LLM API Key is missing. Please configure .env file.",
                "confidence": 0.0
            }

        try:
            base64_image = self.encode_image(image_path)
            
            prompt = f"""
            This represents a car engine part: '{part_name}'.
            An AI model (YOLO) detected it as '{yolo_pred}' but with low confidence ({yolo_conf:.2f}).
            
            Please analyze the image carefully:
            1. Is this component Normal or Abnormal (Defective)?
            2. If abnormal, what specific defect do you see? (Crack, Leak, Corrosion, Open, etc.)
            3. Provide a brief diagnosis.
            
            Response Format (JSON):
            {{
                "status": "Normal" or "Abnormal",
                "defect_type": "None" or "Specific Defect",
                "description": "Brief explanation"
            }}
            """

            response = client.chat.completions.create(
                model="gpt-4o",  # 또는 gpt-4-turbo
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert automotive mechanic AI. Analyze engine parts for defects."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            # 응답 파싱 (간단히 텍스트로 반환)
            llm_result = response.choices[0].message.content
            return {
                "source": "LLM (GPT-4o)",
                "status": "Analyzed",
                "description": llm_result,
                "confidence": 1.0  # LLM 판단은 신뢰도 1.0으로 가정 (또는 별도 추출)
            }
            
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return {
                "source": "LLM_ERROR",
                "description": str(e),
                "status": "Error",
                "confidence": 0.0
            }

    def diagnose(self, part_name, image_path, threshold=0.7):
        """
        하이브리드 진단 수행
        :param part_name: 부품 이름 (e.g., 'Battery')
        :param image_path: 이미지 파일 경로
        :param threshold: YOLO 신뢰도 임계값 (이보다 낮으면 LLM 사용)
        """
        if part_name not in self.models:
            return {"error": f"Model for {part_name} not loaded."}
            
        # 1. YOLO Inference
        model = self.models[part_name]
        results = model(image_path, verbose=False)
        
        # Top-1 결과 추출
        top1_idx = results[0].probs.top1
        top1_conf = results[0].probs.top1conf.item()
        pred_class = results[0].names[top1_idx]  # 'normal' or 'abnormal' (클래스명에 따라 다름)
        
        print(f"[{part_name}] YOLO Prediction: {pred_class} ({top1_conf:.4f})")
        
        # 2. Threshold Check
        if top1_conf >= threshold:
            # 신뢰도가 높으면 YOLO 결과 그대로 사용 (Low Cost)
            return {
                "source": "YOLOv8-cls",
                "status": pred_class,
                "confidence": top1_conf,
                "description": f"Detected {pred_class} with high confidence.",
                "cost": "Free"
            }
        else:
            # 신뢰도가 낮으면 LLM 호출 (High Cost)
            print(f"  -> Low confidence (< {threshold}). Calling LLM for second opinion...")
            llm_result = self.ask_llm(image_path, part_name, pred_class, top1_conf)
            llm_result["cost"] = "Paid"
            return llm_result

# 테스트 실행 코드
if __name__ == "__main__":
    # 프로젝트 루트 가정
    PROJECT_ROOT = Path(r"C:\Users\301\Desktop\AI-5-main-project")
    MODELS_DIR = PROJECT_ROOT / "runs" / "cls"
    
    # 진단기 초기화
    diagnostician = HybridDiagnostician(MODELS_DIR)
    
    # 테스트 이미지 (실제 복사한 파일 사용)
    test_img = PROJECT_ROOT / "img_battery_defect.jpg"
    
    if test_img.exists():
        print(f"\n[Test] Diagnosing {test_img}...")
        # Battery 부품에 대해 진단 요청 (Threshold 0.9로 설정하여 LLM 호출 유도 테스트 가능)
        result = diagnostician.diagnose("Battery", str(test_img), threshold=0.7)
        
        print("\n=== Diagnosis Result ===")
        print(f"Source: {result['source']}")
        print(f"Status: {result['status']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Description: {result['description']}")
    else:
        print(f"[Error] Test image not found at {test_img}")
