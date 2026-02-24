# ai/scripts/audio/benchmark_all.py
"""
[파일 용도] 통합 벤치마크 결과 비교 (레거시)
이전에 개별 모델의 메트릭(metrics.json)을 모아서 비교표를 출력하던 스크립트입니다.
현재는 `evaluate_all_vision.py` 등이 더 최신 기능을 제공할 수 있으나, 과거 실험 결과 비교를 위해 유지됩니다.
"""
import os, json, glob

# 프로젝트 루트 기준 절대경로로 고정 (실행 위치와 무관하게 동작)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))                  # ai/scripts/audio
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", "..", ".."))  # 프로젝트 루트
SAVE_ROOT = os.path.join(_PROJECT_ROOT, "ai", "runs")

def load_all_metrics():
    results = []
    pattern = os.path.join(SAVE_ROOT, "*", "metrics.json")
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            results.append(data)
    return results

def print_table(results):
    if not results:
        print("⚠️  No metrics found in ai/runs/*/metrics.json", flush=True)
        return

    print(f"\n{'='*120}", flush=True)
    print(f"📊 Audio Model Benchmark Results", flush=True)
    print(f"{'='*120}", flush=True)

    # Header (Abnormal Recall is hidden from UI but kept in JSON)
    header = f"{'Model':<25} {'Mode':<10} {'Abn F1':>7} | {'Macro F1':>8} {'Acc':>7} | {'FPR@99.7':>8} {'TRR':>7} {'NRS':>7} {'Div':>6} | {'ms':>6} {'MB':>5}"
    print(header, flush=True)
    print("-" * 115, flush=True)

    for r in results:
        model = r.get("model", "?")
        mode = r.get("mode", "?")
        abn_p = r.get("abnormal_precision", 0)
        abn_f1 = r.get("abnormal_f1", 0)
        t_f1 = r.get("type_macro_f1", 0)
        t_acc = r.get("type_acc", 0)
        
        # Advanced Metrics
        fpr997 = r.get("fpr_at_p99.7", 0)
        trr = r.get("trr", 0)
        nrs = r.get("nrs", 0)
        div = r.get("divergence", 0)
        
        latency = r.get("latency_ms", 0)
        size = r.get("model_size_mb", 0)

        row = f"{model:<25} {mode:<10} {abn_f1:>7.4f} | {t_f1:>8.4f} {t_acc:>7.4f} | {fpr997:>8.4f} {trr:>7.4f} {nrs:>7.4f} {div:>6.2f} | {latency:>6.1f} {size:>5.1f}"
        print(row, flush=True)

    print(f"{'='*115}", flush=True)

    # Best model recommendation (Mean of Abnormal F1, Type Macro F1, and Type Accuracy)
    best = max(results, key=lambda x: (x.get("abnormal_f1", 0) + x.get("type_macro_f1", 0) + x.get("type_acc", 0)) / 3)
    best_combined = (best.get("abnormal_f1", 0) + best.get("type_macro_f1", 0) + best.get("type_acc", 0)) / 3
    print(f"\n🏆 Best: {best['model']} ({best['mode']}) — Balanced Score: {best_combined:.4f} (F1+Acc Avg)", flush=True)

    # Deployment recommendation
    cnn_ft = next((r for r in results if r.get("model") == "cnn14" and r.get("mode") == "finetune"), None)
    if cnn_ft and best["model"] != "cnn14":
        cnn_combined = (cnn_ft.get("abnormal_f1", 0) + cnn_ft.get("type_macro_f1", 0) + cnn_ft.get("type_acc", 0)) / 3
        diff = (best_combined - cnn_combined) * 100
        print(f"\n📏 CNN14 Fine-tune vs Best: {diff:+.1f}% difference", flush=True)
        if diff <= 3:
            print("  → CNN14 + ONNX INT8 배포 추천 (속도 우선)", flush=True)
        elif diff <= 5:
            print("  → CNN14 + ONNX INT8 배포 + 서버 백업(AST/PaSST)", flush=True)
        else:
            print(f"  → {best['model']} + ONNX INT8 서버 배포 추천", flush=True)

    print("", flush=True)


if __name__ == "__main__":
    results = load_all_metrics()
    print_table(results)
