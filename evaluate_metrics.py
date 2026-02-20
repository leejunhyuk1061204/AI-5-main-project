
from ultralytics import YOLO
from pathlib import Path
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
import pandas as pd
import os

# 설정
DATA_ROOT = Path(r"C:\Users\301\Desktop\data\classification")
MODELS_ROOT = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\cls")

# 대상 부품 목록 (8종)
TARGET_PARTS = [
    "ABS_Unit", "Air_Filter_Cover", "Battery", "Brake_Fluid", 
    "Engine_Cover", "Engine_Oil_Fill_Cap", "Radiator", "Windshield_Wiper_Fluid"
]

results_list = []

print("=== Evaluating 8 Models (Calculating Precision, Recall(TPR), FPR, F1) ===")

for part in TARGET_PARTS:
    print(f"\n[Processing] {part}...")
    
    # 모델 로드
    model_path = MODELS_ROOT / part / "weights" / "best.pt"
    if not model_path.exists():
        print(f"  [Error] Model not found for {part}")
        continue
        
    model = YOLO(model_path)
    
    # 검증 데이터셋 경로
    val_dir = DATA_ROOT / part / "val"
    if not val_dir.exists():
        print(f"  [Error] Val dataset not found for {part}")
        continue
        
    # Validation 수행 (Top-1 Accuracy 등 기본 지표 포함)
    # confusion_matrix를 직접 뽑기 위해 val 예측을 수행
    
    # 1. Image List & True Labels 가져오기
    # 구조: val/normal, val/abnormal
    # 0: normal, 1: abnormal (또는 알파벳순 - YOLO는 폴더명 알파벳순으로 클래스 ID 매김)
    # 확인: model.names 출력 필요
    
    class_names = model.names
    # class_names 예: {0: 'abnormal', 1: 'normal'} (ABNORMAL이 알파벳순 앞에 옴)
    
    # 중요: Abnormal(불량)을 Positive(1)로, Normal(정상)을 Negative(0)로 정의해야
    # Precision, Recall, FPR 의미가 맞음.
    # YOLO의 class index는 알파벳순: abnormal -> 0, normal -> 1
    
    y_true = []
    y_pred = []
    
    # Normal 폴더 (Negative, 0) -> 하지만 YOLO에서는 index 1일 가능성 높음
    normal_dir = val_dir / "normal"
    abnormal_dir = val_dir / "abnormal"
    
    # 파일 수집
    normal_files = list(normal_dir.glob("*.*"))
    abnormal_files = list(abnormal_dir.glob("*.*"))
    
    print(f"  - Files: Normal={len(normal_files)}, Abnormal={len(abnormal_files)}")
    
    # 추론 (Batch Inference)
    # Normal Images
    if normal_files:
        results_norm = model(normal_files, verbose=False)
        for r in results_norm:
            pred_cls_idx = r.probs.top1
            pred_cls_name = r.names[pred_cls_idx]
            
            y_true.append("normal")
            y_pred.append(pred_cls_name)

    # Abnormal Images (Positive)
    if abnormal_files:
        results_abnorm = model(abnormal_files, verbose=False)
        for r in results_abnorm:
            pred_cls_idx = r.probs.top1
            pred_cls_name = r.names[pred_cls_idx]
            
            y_true.append("abnormal")
            y_pred.append(pred_cls_name)
            
    # 지표 계산
    # Positive Label = 'abnormal' (불량)
    # Negative Label = 'normal' (정상)
    
    # Confusion Matrix layout:
    #                 Predicted
    #                 Abnormal(P)   Normal(N)
    # Actual Abnormal(P)    TP            FN
    # Actual Normal(N)      FP            TN
    
    labels = ["abnormal", "normal"] # 0, 1 순서 조심
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    tp = cm[0, 0] # Actual Abnormal, Pred Abnormal
    fn = cm[0, 1] # Actual Abnormal, Pred Normal (Miss)
    fp = cm[1, 0] # Actual Normal, Pred Abnormal (False Alarm)
    tn = cm[1, 1] # Actual Normal, Pred Normal
    
    # Accuracy
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    
    # Precision (정밀도) = TP / (TP + FP) -> 불량이라고 한 것 중 진짜 불량
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    
    # Recall (재현율, TPR) = TP / (TP + FN) -> 진짜 불량 중 몆 개나 잡았나
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    tpr = recall
    
    # F1-Score
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # FPR (False Positive Rate) = FP / (FP + TN) -> 정상 중 오탐(불량) 비율
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    
    # FNR (False Negative Rate) = FN / (FN + TP) -> 불량 중 미탐(정상) 비율 (1 - Recall)
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
    
    print(f"  - Conf Matrix: TP={tp}, FN={fn}, FP={fp}, TN={tn}")
    print(f"  - Acc: {acc:.4f}, Prec: {precision:.4f}, Rec(TPR): {recall:.4f}, FPR: {fpr:.4f}")
    
    results_list.append({
        "Part": part,
        "Accuracy": round(acc, 4),
        "Precision": round(precision, 4),
        "TPR (Recall)": round(tpr, 4),
        "FPR (Overkill)": round(fpr, 4),
        "FNR (Leak)": round(fnr, 4),
        "F1-Score": round(f1, 4),
        "TP": tp, "FN": fn, "FP": fp, "TN": tn
    })

# DataFrame 출력
df = pd.DataFrame(results_list)
print("\n=== Final Evaluation Results ===")
print(df.to_string())

# CSV 저장
df.to_csv(r"C:\Users\301\Desktop\AI-5-main-project\evaluation_metrics.csv", index=False)
print("\nSaved to C:\\Users\\301\\Desktop\\AI-5-main-project\\evaluation_metrics.csv")
