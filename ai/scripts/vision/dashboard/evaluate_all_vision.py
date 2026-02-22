
# ai/scripts/vision/dashboard/evaluate_all_vision.py
import os
import json
import glob
import pandas as pd
import subprocess
import argparse
import sys
from datetime import datetime

# Path Configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Project Root: .../ai/scripts/vision/dashboard -> .../ (Up 4 levels: dashboard, vision, scripts, ai)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../../../"))
RUNS_DIR = os.path.join(PROJECT_ROOT, "ai/runs")

# Scripts to run
SCRIPTS = [
    "train_router_effnet.py",
    "train_router_mobilenet.py",
    "train_router_yolo.py"
]

def run_pipeline(test_mode=False, eval_only=False):
    """
    Execute Training -> Benchmark pipeline
    """
    print(f"\n🚀 Starting Vision Benchmark Pipeline")
    print(f"   Test Mode: {test_mode}")
    print(f"   Eval Only: {eval_only}")
    print("=" * 80)
    
    results_status = []

    # 1. Training Phase
    if not eval_only:
        print("\n📦 [Phase 1] Training Models...")
        epochs = 1 if test_mode else 50
        for script in SCRIPTS:
            script_path = os.path.join(CURRENT_DIR, script)
            cmd = [sys.executable, script_path, "--epochs", str(epochs)]
            
            print(f"   ▶️  Training: {script} (Epochs={epochs})")
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
                subprocess.run(cmd, check=True, env=env)
                results_status.append({"Model": script, "Phase": "Train", "Status": "SUCCESS"})
            except Exception as e:
                print(f"   ❌ Training Failed: {e}")
                results_status.append({"Model": script, "Phase": "Train", "Status": "FAIL", "Error": str(e)})

    # 2. Benchmark Phase (Latency/Acc/Params)
    print("\n⏱️  [Phase 2] Benchmarking (Evaluation)...")
    for script in SCRIPTS:
        script_path = os.path.join(CURRENT_DIR, script)
        cmd = [sys.executable, script_path, "--benchmark"]
        
        print(f"   ▶️  Benchmarking: {script}")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
            subprocess.run(cmd, check=True, env=env)
            results_status.append({"Model": script, "Phase": "Benchmark", "Status": "SUCCESS"})
        except Exception as e:
            print(f"   ❌ Benchmark Failed: {e}")
            results_status.append({"Model": script, "Phase": "Benchmark", "Status": "FAIL", "Error": str(e)})

    return results_status

def load_metrics(status_list):
    """Load benchmark metrics and merge with status"""
    pattern = os.path.join(RUNS_DIR, "router_benchmark_*.json")
    files = glob.glob(pattern)
    
    data = []
    
    # Helper to check if model failed
    def get_status(model_script_name):
        # rough matching
        for s in status_list:
            if s["Phase"] == "Benchmark" and s["Model"] in model_script_name: # simplistic
                return s["Status"]
        return "UNKNOWN"

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                metric = json.load(f)
                
                # Check consistency
                if metric.get("mode") != "benchmark":
                    continue # Skip old or training logs
                
                item = {
                    "Model": metric.get("model", "Unknown"),
                    "Acc (Top-1)": metric.get("accuracy", 0.0),
                    "Latency (ms)": metric.get("latency_ms", 0.0),
                    "Params (M)": metric.get("params", 0) / 1e6,
                    "Size (MB)": metric.get("size_mb", 0.0),
                    "FLOPs (G)": metric.get("flops_g", 0.0),
                    "Device": metric.get("latency_device", "N/A"),
                    "Status": "SUCCESS"
                }
                data.append(item)
        except Exception as e:
            print(f"⚠️ Error loading {fpath}: {e}")
            
    # Add Failures explicitly if needed, but for now we look at json files.
    # If a script failed, json might not exist.
    # Let's add failed scripts to data
    for s in status_list:
        if s["Phase"] == "Benchmark" and s["Status"] == "FAIL":
            data.append({
                "Model": s["Model"],
                "Status": "FAIL",
                "Error": s.get("Error", "Unknown")
            })
            
    return data

def generate_report(data):
    if not data:
        print("❌ No benchmark data found.")
        return

    df = pd.DataFrame(data)
    
    # Sort
    if "Acc (Top-1)" in df.columns:
        df = df.sort_values(by=["Acc (Top-1)", "Latency (ms)"], ascending=[False, True])
    
    print("\n" + "="*100)
    print("📋 FINAL BENCHMARK REPORT")
    print("="*100)
    print(df.to_string(index=False))
    print("="*100)
    
    # Save CSV
    csv_path = os.path.join(RUNS_DIR, "vision_benchmark_summary.csv")
    df.to_csv(csv_path, index=False)
    print(f"💾 Report saved to {csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run in test mode (1 epoch)")
    parser.add_argument("--eval-only", action="store_true", help="Skip training, run benchmark only")
    args = parser.parse_args()
    
    status = run_pipeline(test_mode=args.test, eval_only=args.eval_only)
    data = load_metrics(status)
    generate_report(data)
    
    print("\n" + "="*80)
    print(f"📊 Dashboard Vision Model Consolidate Report ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*80)
    
    # Text Table
    print(df.to_string(index=False, float_format="%.4f"))
    
    print("\n" + "="*80)
    print("🏆 Recommendation (Top 3)")
    print("-" * 80)
    
    df_valid = df[df["Top-1 Acc"] > 0]
    if len(df_valid) > 0:
        for i, (_, row) in enumerate(df_valid.head(3).iterrows()):
            print(f"{i+1}. {row['Model']} | Acc: {row['Top-1 Acc']:.4f} | {row['Latency (ms)']:.1f}ms | {row['Size (MB)']:.1f}MB")
    else:
        print("No valid models trained yet.")

    print("="*80 + "\n")
    
    # Save CSV
    report_path = os.path.join(RUNS_DIR, "dashboard_benchmark_summary.csv")
    df.to_csv(report_path, index=False)
    print(f"📄 Full report saved to: {report_path}")

