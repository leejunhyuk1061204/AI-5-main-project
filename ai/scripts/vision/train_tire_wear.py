# ai/scripts/train_tire_wear.py
"""
타이어 마모도(%) 소수점 단위 정밀 예측 모델 학습 도구 (Tire Wear Regressor)

[기획 및 설계]
1. 정밀 진단: YOLO가 "마모됨"을 찾으면, 이 모델은 "정확히 몇 %"인지를 수치로 출력합니다.
2. 데이터 연동: sync_active_learning.py를 통해 수집된 JSON 데이터의 'wear_level_pct' 값을 정답(Target)으로 사용합니다.
3. 학습 시점: LLM이 생성한 정답 데이터가 500장 이상 S3에 쌓였을 때 학습을 권장합니다.

[사용법]
python ai/scripts/train_tire_wear.py --epochs 50 --batch 32
"""
import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image
from pathlib import Path

# =============================================================================
# [설정] 런팟(RunPod) 환경 최적화
# =============================================================================
DATA_DIR = Path("ai/data/yolo/tire") # 동기화된 데이터 경로
JSON_DIR = Path("ai/data/tire/retrain") # LLM 정답 JSON 경로 (데이터가 쌓이면 생성됨)
OUTPUT_DIR = Path("ai/runs/tire_wear_model")
SAVE_PATH = Path("ai/weights/tire/wear_model.pth")

DEVICE = torch.device("cuda" if torch.cuda.org.is_available() else "cpu")

# =============================================================================
# 1. 커스텀 데이터셋: 이미지와 % 수치를 쌍으로 로드
# =============================================================================
class TireWearDataset(Dataset):
    def __init__(self, json_dir, transform=None):
        self.samples = []
        self.transform = transform
        
        if not os.path.exists(json_dir):
            return

        for json_file in Path(json_dir).glob("*.json"):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                wear_pct = data.get("wear_level_pct")
                img_url = data.get("source_url")
                
                if wear_pct is not None and img_url:
                    # S3 URL에서 파일명 추출 (sync 스크립트가 이미지를 이 이름으로 저장함)
                    file_id = os.path.basename(img_url).split('.')[0]
                    # 로컬에 다운로드된 이미지 경로 찾기 (normal 또는 cracked 폴더 아래에 있음)
                    img_path = list(DATA_DIR.glob(f"**/{file_id}.*"))
                    
                    if img_path:
                        self.samples.append((str(img_path[0]), float(wear_pct)))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert('RGB')
        if self.transform:
            image = self.transform(image)
        return image, torch.tensor([label], dtype=torch.float32)

# =============================================================================
# 2. 회귀 모델 구성 (EfficientNet + Linear Head)
# =============================================================================
class TireWearModel(nn.Module):
    def __init__(self):
        super().__init__()
        # 경량이지만 강력한 EfficientNet-B0 사용
        self.backbone = models.efficientnet_b0(pretrained=True)
        # 마지막 레이어를 0~100 사이의 숫자를 내뱉는 회귀 레이어로 교체
        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(p=0.2, inplace=True),
            nn.Linear(in_features, 1) # 정답은 오직 하나 (마모도 %)
        )

    def forward(self, x):
        return self.backbone(x)

# =============================================================================
# 3. 학습 루프 (현재는 템플릿이며, 데이터가 충분할 때 주석을 해제하고 실행하세요)
# =============================================================================
def train():
    print(f"\n[Future Ready] 타이어 마모도 회귀 모델 학습 템플릿")
    print(f"  - 현재 데이터 확인 중: {JSON_DIR}")
    
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    dataset = TireWearDataset(JSON_DIR, transform=transform)
    
    if len(dataset) < 10:
        print(f"\n[⚠️ 학습 중지] 현재 수집된 숫자 정답 데이터가 {len(dataset)}개로 너무 적습니다.")
        print(f"  - 최소 100개 이상의 LLM Confirmed 데이터가 쌓인 후 실행하세요.")
        return

    loader = DataLoader(dataset, batch_size=16, shuffle=True)
    model = TireWearModel().to(DEVICE)
    criterion = nn.MSELoss() # 수치 오차를 줄이는 손실 함수
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print(f"🚀 학습 시작... (샘플 수: {len(dataset)})")
    
    # --- 실제 학습 부분 (필요 시 주석 해제하여 사용 가능) ---
    # for epoch in range(50):
    #     model.train()
    #     for imgs, labels in loader:
    #         imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
    #         outputs = model(imgs)
    #         loss = criterion(outputs, labels)
    #         optimizer.zero_grad()
    #         loss.backward()
    #         optimizer.step()
    #     print(f"Epoch {epoch+1} Loss: {loss.item():.4f}")
    
    # os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
    # torch.save(model.state_dict(), SAVE_PATH)
    # print(f"✅ 모델 저장 완료: {SAVE_PATH}")

# [⚠️ 현재 비활성화됨] 데이터가 충분히 쌓인 후(최소 500장 이상) 아래 주석을 풀고 사용하세요.

# if __name__ == "__main__":
#     train()
