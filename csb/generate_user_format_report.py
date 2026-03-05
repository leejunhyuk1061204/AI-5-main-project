from ultralytics import YOLO
import torch
from pathlib import Path
import pandas as pd
import os

def get_latest_model(comp_name):
    base_runs = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\classify\runs\train_analyze")
    
    # Priority for specialized final models
    priority_names = [f"{comp_name}_v7_final", f"{comp_name}_retrained", comp_name]
    
    for name in priority_names:
        model_p = base_runs / name / "weights" / "best.pt"
        if model_p.exists():
            return str(model_p)
    return None

def generate_user_report():
    data_root = Path(r"C:\Users\301\Desktop\data\classification")
    components = sorted([d.name for d in data_root.iterdir() if d.is_dir()])
    
    thresholds = [0.3, 0.5]
    all_data = []

    for comp in components:
        model_path = get_latest_model(comp)
        test_dir = data_root / comp / "test"
        
        if not model_path or not test_dir.exists():
            continue
            
        model = YOLO(model_path)
        
        # Determine abnormal class index (usually 0)
        abnormal_idx = 0
        for idx, name in model.names.items():
            if 'abnormal' in name.lower():
                abnormal_idx = idx
                break
        
        for thresh in thresholds:
            tp, fn, tn, fp = 0, 0, 0, 0
            
            # Eval Abnormal
            ab_imgs = list((test_dir / "abnormal").glob("*.*"))
            for img in ab_imgs:
                res = model.predict(str(img), verbose=False)[0]
                if res.probs.data[abnormal_idx].item() >= thresh: tp += 1
                else: fn += 1
                
            # Eval Normal
            norm_imgs = list((test_dir / "normal").glob("*.*"))
            for img in norm_imgs:
                res = model.predict(str(img), verbose=False)[0]
                if res.probs.data[abnormal_idx].item() >= thresh: fp += 1
                else: tn += 1
            
            total = tp + tn + fp + fn
            accuracy = (tp + tn) / total if total > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
            
            # Judgment logic
            if recall >= 0.9 and fnr <= 0.1:
                judgment = "✅ 합격 (우수)"
            elif recall >= 0.7:
                judgment = "⚠️ 보완 권장 (양호)"
            else:
                judgment = "❌ 재학습 필요"

            all_data.append({
                "부품명 (Component)": comp,
                "임계값": thresh,
                "정확도": f"{accuracy:.1%}",
                "정밀도": f"{precision:.1%}",
                "재현율": f"{recall:.1%}",
                "과검 (FPR)": f"{fpr:.1%}",
                "미검 (FNR)": f"{fnr:.1%}",
                "판정": judgment
            })
            
    return pd.DataFrame(all_data)

if __name__ == "__main__":
    df = generate_user_report()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print("\n" + "="*120)
    print("전체 부품 최종 성능 성적표 (Test Set 기준)")
    print("="*120)
    print(df.to_string(index=False))
    print("="*120)
