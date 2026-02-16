# ai/scripts/audio/benchmark_all.py
"""
📊 전 모델 벤치마크 결과 종합 비교표

[Usage]
  python -m ai.scripts.audio.benchmark_all
"""
import os, json, glob

SAVE_ROOT = "./ai/runs"

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

    # Header
    header = f"{'Model':<25} {'Mode':<10} {'Recall':>7} {'Abn F1':>7} | {'starter':>7} {'engine':>7} {'brake':>7} {'Macro F1':>8} | {'Uncert%':>7} | {'ms':>6} {'MB':>5}"
    print(header, flush=True)
    print("-" * 125, flush=True)

    for r in results:
        model = r.get("model", "?")
        mode = r.get("mode", "?")
        abn_r = r.get("abnormal_recall", 0)
        abn_f1 = r.get("abnormal_f1", 0)
        t_f1 = r.get("type_macro_f1", 0)
        uncert = r.get("uncertain_pct", 0)
        latency = r.get("latency_ms", 0)
        size = r.get("model_size_mb", 0)

        # Per-class
        starter_f1 = r.get("starter_f1", "-")
        engine_f1 = r.get("engine_f1", "-")
        brake_f1 = r.get("brake_f1", "-")

        s_str = f"{starter_f1:>7.4f}" if isinstance(starter_f1, (float, int)) else f"{starter_f1:>7}"
        e_str = f"{engine_f1:>7.4f}" if isinstance(engine_f1, (float, int)) else f"{engine_f1:>7}"
        b_str = f"{brake_f1:>7.4f}" if isinstance(brake_f1, (float, int)) else f"{brake_f1:>7}"

        row = f"{model:<25} {mode:<10} {abn_r:>7.4f} {abn_f1:>7.4f} | {s_str} {e_str} {b_str} {t_f1:>8.4f} | {uncert:>7.1f}% | {latency:>6.1f} {size:>5.1f}"
        print(row, flush=True)

    print(f"{'='*125}", flush=True)

    # Best model recommendation
    best = max(results, key=lambda x: (x.get("abnormal_f1", 0) + x.get("type_macro_f1", 0)) / 2)
    best_combined = (best.get("abnormal_f1", 0) + best.get("type_macro_f1", 0)) / 2
    print(f"\n🏆 Best: {best['model']} ({best['mode']}) — Combined F1: {best_combined:.4f}", flush=True)

    # Deployment recommendation
    cnn_ft = next((r for r in results if r.get("model") == "cnn14" and r.get("mode") == "finetune"), None)
    if cnn_ft and best["model"] != "cnn14":
        cnn_combined = (cnn_ft.get("abnormal_f1", 0) + cnn_ft.get("type_macro_f1", 0)) / 2
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
