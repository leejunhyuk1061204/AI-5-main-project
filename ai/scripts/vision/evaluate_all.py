import os
import argparse
import numpy as np
import pandas as pd
from ultralytics import YOLO
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, auc, roc_auc_score, precision_recall_curve
import matplotlib.pyplot as plt
import seaborn as sns
import torch

# Set backend to Agg
plt.switch_backend('Agg')

# Paths
WEIGHTS_DIR = "ai/weights"
DATA_DIR = "ai/data/yolo"

# Model Configs with Comparison Support
MODELS = {
    "exterior": {
        "base": "yolov8n.pt",
        "trained": os.path.join(WEIGHTS_DIR, "exterior/best.pt"),
        "data": os.path.join(DATA_DIR, "exterior/data.yaml"),
        "type": "detection",
        "task": "1. 외관 (Exterior)"
    },
    "engine": {
        "base": "yolov8s.pt",
        "trained": os.path.join(WEIGHTS_DIR, "engine/best.pt"),
        "data": os.path.join(DATA_DIR, "engine/data.yaml"),
        "type": "detection",
        "task": "2. 엔진룸 (Engine)"
    },
    "dashboard": {
        "base": "yolov8n.pt",
        "trained": os.path.join(WEIGHTS_DIR, "dashboard/best.pt"),
        "data": os.path.join(DATA_DIR, "dashboard/data.yaml"),
        "type": "detection",
        "task": "3. 대시보드 (Dash)"
    },
    "tire": {
        "base": "yolov8s-cls.pt",
        "trained": os.path.join(WEIGHTS_DIR, "tire/best.pt"),
        "data": os.path.join(DATA_DIR, "tire"), 
        "type": "classification",
        "task": "4. 타이어 (Tire)"
    }
}

def log_debug(msg):
    print(f"[DEBUG] {msg}", flush=True)

def save_confusion_matrix(cm, classes, filename, title="Confusion Matrix"):
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt=".0f", cmap="Blues",
                xticklabels=classes, yticklabels=classes)
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    return filename

def eval_detection(name, data_path, model_path, label="Ours"):
    print(f"\n🚀 Evaluating {name.upper()} ({label}) Model (Detection)...", flush=True)
    
    # Handle missing model
    if not os.path.exists(model_path) and not model_path.endswith(".pt"): 
        # Base models like yolov8n.pt might be downloaded automatically, so we let YOLO handle it if it's a name
        pass
    elif not os.path.exists(model_path) and os.path.sep in model_path:
        print(f"❌ Model file not found: {model_path}")
        return {}

    try:
        model = YOLO(model_path)
        # Validation
        results = model.val(data=data_path, split="test", verbose=True, plots=False)
        
        metrics = {}
        metrics["mAP50"] = results.box.map50
        metrics["mAP50-95"] = results.box.map
        metrics["Precision"] = results.box.mp
        metrics["Recall"] = results.box.mr
        
        # Specific Logic
        if name == "exterior" and label == "Ours":
             if hasattr(results, 'confusion_matrix'):
                cm = results.confusion_matrix.matrix
                names = [results.names[i] for i in range(len(results.names))]
                fname = f"{name}_{label}_cm.png"
                save_confusion_matrix(cm, names, fname, title=f"Exterior ({label}) Confusion Matrix")
                metrics["cm_img"] = fname

        elif name == "engine":
            metrics["mAP75"] = results.box.map75
            
        elif name == "dashboard" and label == "Ours":
             # Threshold Optimization
             try:
                 # Check access to curves
                 # p_curve, r_curve, f1_curve are attributes of DetMetrics.box (BoxMetrics)
                 # But in recent ultralytics, they might not be directly exposed as simple arrays in the wrapper?
                 # Actually results.box.p_curve is valid.
                 f1_curve = results.box.f1_curve
                 best_idx = np.argmax(f1_curve)
                 best_conf = np.linspace(0, 1, len(f1_curve))[best_idx]
                 metrics["best_conf"] = best_conf
                 metrics["best_f1"] = f1_curve[best_idx]
                 
                 # Plot PR Curve - P and R vs Conf
                 # Actually Standard PR Curve is Precision on y, Recall on x
                 # But let's plot P & R vs Confidence as requested ("Conf vs Recall Curve")
                 plt.figure(figsize=(8,6))
                 x_axis = np.linspace(0, 1, len(results.box.p_curve))
                 plt.plot(x_axis, results.box.p_curve, label="Precision")
                 plt.plot(x_axis, results.box.r_curve, label="Recall")
                 plt.axvline(x=best_conf, color='r', linestyle='--', label=f"Best Conf {best_conf:.2f}")
                 plt.xlabel("Confidence")
                 plt.ylabel("Score")
                 plt.title(f"Dashboard ({label}) P-R vs Confidence")
                 plt.legend()
                 plt.grid()
                 fname = f"{name}_{label}_pr_conf_curve.png"
                 plt.savefig(fname)
                 plt.close()
                 metrics["pr_curve_img"] = fname
             except Exception as e:
                 print(f"[Warning] Could not extract curve data: {e}")

        return metrics
    except Exception as e:
        print(f"❌ Error during evaluation of {model_path}: {e}")
        return {}

def eval_classification(name, data_path, model_path, label="Ours"):
    print(f"\n🚀 Evaluating {name.upper()} ({label}) Model (Classification)...", flush=True)
    
    # Handle path logic similar to detection
    if os.path.sep in model_path and not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        return {}

    try:
        model = YOLO(model_path)
        test_dir = os.path.join(data_path, "test")
        if not os.path.exists(test_dir):
            print(f"❌ Test directory not found: {test_dir}")
            return {}
        
        true_labels = []
        pred_labels = []
        pred_probs = [] 
        
        classes = model.names
        print(f"   - Classes: {classes}")
        
        # Identify Danger vs Normal
        # If Base model (ImageNet) is used, classes will be 1000 imagenet classes.
        # This comparison will be meaningless but requested.
        # We try to map, but likely it will fail or we just treat everything not-normal as danger?
        # Actually for Baseline (Raw), we can just skip detailed custom metrics if classes don't match.
        
        is_custom_model = (len(classes) <= 10) # Simple heuristic. ImageNet has 1000.
        
        if not is_custom_model:
            print(f"   ⚠️ Baseline model has {len(classes)} classes. Skipping specific tire metrics.")
            return {"roc_auc": 0.0, "danger_recall": 0.0}

        # Logic for Custom Model
        normal_keys = [k for k, v in classes.items() if 'normal' in v.lower()]
        danger_keys = [k for k, v in classes.items() if 'normal' not in v.lower()]
        
        normal_idx = normal_keys[0] if normal_keys else 0
        danger_idx = danger_keys[0] if danger_keys else 1
        
        for class_name in os.listdir(test_dir):
            class_dir = os.path.join(test_dir, class_name)
            if not os.path.isdir(class_dir): continue
            
            # Map folder name to ID
            # This requires folder name to match model class name
            current_label_key = [k for k, v in classes.items() if v == class_name]
            if not current_label_key: 
                continue
            current_label = current_label_key[0]
            
            for img_name in os.listdir(class_dir):
                if not img_name.lower().endswith(('.png', '.jpg', '.jpeg')): continue
                img_path = os.path.join(class_dir, img_name)
                
                res = model.predict(img_path, verbose=False)[0]
                probs = res.probs.data.cpu().numpy()
                
                pred_idx = np.argmax(probs)
                true_labels.append(current_label)
                pred_labels.append(pred_idx)
                pred_probs.append(probs[danger_idx])

        # Metrics
        target_names = [classes[i] for i in sorted(classes.keys())]
        cm = confusion_matrix(true_labels, pred_labels)
        
        metrics = {}
        
        # Only generating plots for 'Ours' to reduce clutter, or both? 
        # User asked for comparison tables. Plots for Ours is most critical.
        if label == "Ours":
            fname_cm = f"{name}_{label}_cm.png"
            save_confusion_matrix(cm, target_names, fname_cm, title=f"Tire ({label}) Confusion Matrix")
            metrics["cm_img"] = fname_cm
            
            binary_true = [1 if x == danger_idx else 0 for x in true_labels]
            if len(set(binary_true)) > 1:
                roc_auc = roc_auc_score(binary_true, pred_probs)
                metrics["roc_auc"] = roc_auc
                
                fpr, tpr, _ = roc_curve(binary_true, pred_probs)
                plt.figure(figsize=(8,6))
                plt.plot(fpr, tpr, label=f"AUC = {roc_auc:.4f}")
                plt.plot([0, 1], [0, 1], 'k--')
                plt.title("Tire ROC Curve")
                plt.legend()
                fname_roc = f"{name}_{label}_roc.png"
                plt.savefig(fname_roc)
                plt.close()
                metrics["roc_img"] = fname_roc
            else:
                metrics["roc_auc"] = 0.0

            # Danger Recall
            metrics["danger_recall"] = classification_report(true_labels, pred_labels, output_dict=True)[classes[danger_idx]]['recall']
        
        return metrics

    except Exception as e:
        print(f"❌ Error during evaluation of {model_path}: {e}")
        return {}

def main():
    log_debug("Script started...")
    
    # We will accumulate rows for a summary table
    summary_data = []
    
    results_markdown = []
    results_markdown.append("# 📊 AI Vision Model Evaluation: Baseline vs Trained")
    results_markdown.append(f"Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    results_markdown.append("\n---")
    
    # 1. Exterior
    cfg = MODELS["exterior"]
    base_res = eval_detection("exterior", cfg["data"], cfg["base"], "Base")
    ours_res = eval_detection("exterior", cfg["data"], cfg["trained"], "Ours")
    
    if ours_res:
        impr = (ours_res.get('mAP50',0) - base_res.get('mAP50',0)) * 100
        summary_data.append(["Exterior (mAP50)", base_res.get('mAP50',0), ours_res.get('mAP50',0), f"{impr:+.2f}%"])
        
        results_markdown.append("\n## 1. Exterior")
        results_markdown.append(f"**Improvement (mAP50)**: {base_res.get('mAP50',0):.4f} → **{ours_res.get('mAP50',0):.4f}** ({impr:+.2f}%)")
        if "cm_img" in ours_res:
            results_markdown.append(f"\n![Confusion Matrix]({ours_res['cm_img']})")

    # 2. Engine
    cfg = MODELS["engine"]
    base_res = eval_detection("engine", cfg["data"], cfg["base"], "Base")
    ours_res = eval_detection("engine", cfg["data"], cfg["trained"], "Ours")
    
    if ours_res:
        impr = (ours_res.get('mAP50',0) - base_res.get('mAP50',0)) * 100
        summary_data.append(["Engine (mAP50)", base_res.get('mAP50',0), ours_res.get('mAP50',0), f"{impr:+.2f}%"])
        
        results_markdown.append("\n## 2. Engine")
        results_markdown.append(f"**Improvement (mAP50)**: {base_res.get('mAP50',0):.4f} → **{ours_res.get('mAP50',0):.4f}** ({impr:+.2f}%)")
        if "mAP75" in ours_res:
            results_markdown.append(f"- **Recall @ IoU=0.75**: {ours_res['mAP75']:.4f}")

    # 3. Dashboard
    cfg = MODELS["dashboard"]
    base_res = eval_detection("dashboard", cfg["data"], cfg["base"], "Base")
    ours_res = eval_detection("dashboard", cfg["data"], cfg["trained"], "Ours")
    
    if ours_res:
        # For dashboard, Recall is key? Or Precision? Let's use mAP50 for summary
        impr = (ours_res.get('mAP50',0) - base_res.get('mAP50',0)) * 100
        summary_data.append(["Dashboard (mAP50)", base_res.get('mAP50',0), ours_res.get('mAP50',0), f"{impr:+.2f}%"])
        
        results_markdown.append("\n## 3. Dashboard")
        results_markdown.append(f"**Improvement (mAP50)**: {base_res.get('mAP50',0):.4f} → **{ours_res.get('mAP50',0):.4f}** ({impr:+.2f}%)")
        if "best_conf" in ours_res:
             results_markdown.append(f"- **Optimal Conf**: {ours_res['best_conf']:.3f}")
        if "pr_curve_img" in ours_res:
             results_markdown.append(f"\n![PR Curve]({ours_res['pr_curve_img']})")

    # 4. Tire
    cfg = MODELS["tire"]
    base_res = eval_classification("tire", cfg["data"], cfg["base"], "Base")
    ours_res = eval_classification("tire", cfg["data"], cfg["trained"], "Ours")
    
    if ours_res:
        impr = (ours_res.get('roc_auc',0) - base_res.get('roc_auc',0)) * 100
        summary_data.append(["Tire (AUC)", base_res.get('roc_auc',0), ours_res.get('roc_auc',0), f"{impr:+.2f}%"])
        
        results_markdown.append("\n## 4. Tire")
        results_markdown.append(f"**Improvement (AUC)**: {base_res.get('roc_auc',0):.4f} → **{ours_res.get('roc_auc',0):.4f}** ({impr:+.2f}%)")
        if "cm_img" in ours_res:
             results_markdown.append(f"\n![Confusion Matrix]({ours_res['cm_img']})")
        if "roc_img" in ours_res:
             results_markdown.append(f"\n![ROC Curve]({ours_res['roc_img']})")
    
    # Final Table
    # Use manual formatting to avoid tabulate dependency
    table_md = "| Task (Metric) | Baseline (Raw) | Ours (Trained) | Improvement |\n"
    table_md += "| :--- | :--- | :--- | :--- |\n"
    for row in summary_data:
        table_md += f"| {row[0]} | {row[1]:.4f} | {row[2]:.4f} | {row[3]} |\n"
    
    # Insert Table at the top of markdown
    results_markdown.insert(3, "\n### 📈 Performance Summary")
    results_markdown.insert(4, table_md)
    
    # Save
    with open("vision_baseline_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(results_markdown))
        
    print(table_md)
    print("\n✅ Comparison Complete. Saved to vision_baseline_report.md")

if __name__ == "__main__":
    main()
