import os
import sys
import torch
import argparse
from datetime import datetime
from ai.scripts.audio.run_all_benchmarks import run_job, BATCH_SIZES, clear_gpu, multi_log_context

def main():
    parser = argparse.ArgumentParser(description="LoRA Comparison Benchmark (PaSST & AST)")
    parser.add_argument("--dry-run", action="store_true", help="Run 1 epoch only")
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs")
    parser.add_argument("--filter", type=str, default=None, help="Filter jobs by name (e.g., 'swa', 'finetune')")
    parser.add_argument("--list", action="store_true", help="List available jobs")
    args = parser.parse_args()

    # Configuration
    dry_run = args.dry_run
    if dry_run:
        epochs_bl = args.epochs if args.epochs else 1
        epochs_ft = args.epochs if args.epochs else 1
        os.environ["BENCHMARK_DRY_RUN"] = "1"
    else:
        epochs_bl = args.epochs if args.epochs else 2   # [v4.8] Minimal Baseline
        epochs_ft = args.epochs if args.epochs else 8   # [v4.8] Lightweight LoRA
        os.environ.pop("BENCHMARK_DRY_RUN", None)

    # 1. Defined Jobs
    jobs = [
        # ── PaSST-S (Standard: No Structured patchout, Stride 16) ──
        {
            "name": "PaSST-S Baseline (Frozen)",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_p16_s16_128_ap468", "--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["passt"]["baseline"])],
        },
        {
            "name": "PaSST-S Fine-tune (LoRA)",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_p16_s16_128_ap468", "--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["passt"]["finetune"])],
        },
        # ── PaSST-S-SWA (Structured patchout + SWA, High Performance) ──
        {
            "name": "PaSST-S-SWA Baseline (Frozen)",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_swa_p16_128_ap476", "--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["passt"]["baseline"])],
        },
        {
            "name": "PaSST-S-SWA Fine-tune (LoRA)",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_swa_p16_128_ap476", "--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["passt"]["finetune"])],
        },
        # ── AST (Comparison) ──
        {
            "name": "AST Baseline (Frozen)",
            "module": "ai.scripts.audio.train_ast",
            "args": ["--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["ast"]["baseline"])],
        },
        {
            "name": "AST Fine-tune (LoRA)",
            "module": "ai.scripts.audio.train_ast",
            "args": ["--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["ast"]["finetune"])],
        },
    ]
    
    # [Filter Logic]
    if args.list:
        print("📋 Available Jobs:", flush=True)
        for i, job in enumerate(jobs):
            print(f"  {i+1}. {job['name']}", flush=True)
        return

    if args.filter:
        original_count = len(jobs)
        jobs = [j for j in jobs if args.filter.lower() in j["name"].lower()]
        print(f"🔍 Filtered jobs: {original_count} -> {len(jobs)} (Query: '{args.filter}')", flush=True)
        if not jobs:
            print("❌ No jobs matched the filter.", flush=True)
            return

    log_path = os.path.join("ai", "runs", "lora_benchmark_log.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    print(f"🚀 Starting LoRA Comparison Benchmark...", flush=True)
    print(f"   - Dry Run: {dry_run}", flush=True)
    print(f"   - Baseline Epochs: {epochs_bl}", flush=True)
    print(f"   - LoRA Epochs: {epochs_ft}", flush=True)

    with open(log_path, "a", encoding="utf-8") as log_file:
        for job in jobs:
            print(f"\n▶️  Running: {job['name']}", flush=True)
            run_job(job, log_file)
            clear_gpu()

    print(f"\n✅ Benchmark Complete! Check ai/runs for results.", flush=True)
    
    # Simple Report Generation
    with open(log_path, "a", encoding="utf-8") as log_file:
        with multi_log_context(log_file):
            print("\n📊 Generating Summary Table...", flush=True)
            from ai.scripts.audio.benchmark_all import load_all_metrics, print_table
            
            # [Fix] Filter out non-target models (like old cnn14 results)
            all_results = load_all_metrics()
            # Loose filtering to allow variants (passt_swa, passt_n_s, etc.)
            filtered_results = [
                r for r in all_results 
                if "passt" in r.get("model", "").lower() or "ast" in r.get("model", "").lower()
            ]
            
            print_table(filtered_results)

if __name__ == "__main__":
    main()
