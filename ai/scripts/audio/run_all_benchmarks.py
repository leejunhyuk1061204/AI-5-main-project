# ai/scripts/audio/run_all_benchmarks.py
"""
🚀 전체 벤치마크 자동 실행 스크립트 (RTX 3050 6GB 최적화)

[사용법]
  Dry-run (1 epoch, 오류 확인):
    python -m ai.scripts.audio.run_all_benchmarks --dry-run

  Full 벤치마크 (자동 학습):
    python -m ai.scripts.audio.run_all_benchmarks

[안전 장치]
- 각 모델은 try/except로 감싸여 있어 하나가 실패해도 다음 모델로 넘어감
- OOM 발생 시 자동으로 배치 크기를 절반으로 줄여 재시도
- GPU 메모리 캐시를 매 실행 전 초기화
- 실시간 로그를 benchmark_log.txt에 기록
"""
import os, sys, gc, time, argparse, traceback
from datetime import datetime, timedelta

import torch

# ──────────── RTX 3050 6GB 최적화 배치 크기 ────────────
# 모델별로 안전한 배치 크기 설정 (6GB VRAM 기준)
BATCH_SIZES = {
    "cnn14":   {"baseline": 16, "finetune": 8},
    "ast":     {"baseline": 8,  "finetune": 4},
    "passt":   {"baseline": 8,  "finetune": 4},
    "hybrid":  {"default": 4},
}

# ──────────── 실행 순서 정의 ────────────
def get_jobs(dry_run=False):
    """학습 작업 목록 생성"""
    epochs_bl = 1 if dry_run else 10    # baseline epochs
    epochs_ft = 1 if dry_run else 20    # finetune epochs
    epochs_hy = 1 if dry_run else 20    # hybrid epochs

    jobs = [
        # ── CNN14 ──
        {
            "name": "CNN14 Baseline",
            "module": "ai.scripts.audio.train_cnn14",
            "args": ["--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["cnn14"]["baseline"])],
        },
        {
            "name": "CNN14 Fine-tune",
            "module": "ai.scripts.audio.train_cnn14",
            "args": ["--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["cnn14"]["finetune"])],
        },
        # ── AST ──
        {
            "name": "AST Baseline",
            "module": "ai.scripts.audio.train_ast",
            "args": ["--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["ast"]["baseline"])],
        },
        {
            "name": "AST Fine-tune",
            "module": "ai.scripts.audio.train_ast",
            "args": ["--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["ast"]["finetune"])],
        },
        # ── PaSST-N-S (No Structured patchout, stride 16) ──
        {
            "name": "PaSST-N-S Baseline",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_p16_s16_128_ap468", "--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["passt"]["baseline"])],
        },
        {
            "name": "PaSST-N-S Fine-tune",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_p16_s16_128_ap468", "--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["passt"]["finetune"])],
        },
        # ── PaSST-S-SWA (Structured patchout + SWA, 최고 성능) ──
        {
            "name": "PaSST-S-SWA Baseline",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_swa_p16_128_ap476", "--mode", "baseline", "--epochs", str(epochs_bl), "--batch_size", str(BATCH_SIZES["passt"]["baseline"])],
        },
        {
            "name": "PaSST-S-SWA Fine-tune",
            "module": "ai.scripts.audio.train_passt",
            "args": ["--arch", "passt_s_swa_p16_128_ap476", "--mode", "finetune", "--epochs", str(epochs_ft), "--batch_size", str(BATCH_SIZES["passt"]["finetune"])],
        },
        # ── Hybrid (Fusions) ──
        {
            "name": "Hybrid (AST+CNN14)",
            "module": "ai.scripts.audio.train_hybrid",
            "args": ["--teacher", "ast", "--epochs", str(epochs_hy), "--batch_size", str(BATCH_SIZES["hybrid"]["default"])],
        },
        {
            "name": "Hybrid (PaSST-N-S+CNN14)",
            "module": "ai.scripts.audio.train_hybrid",
            "args": ["--teacher", "passt_s_p16_s16_128_ap468", "--epochs", str(epochs_hy), "--batch_size", str(BATCH_SIZES["hybrid"]["default"])],
        },
        {
            "name": "Hybrid (PaSST-SWA+CNN14)",
            "module": "ai.scripts.audio.train_hybrid",
            "args": ["--teacher", "passt_s_swa", "--epochs", str(epochs_hy), "--batch_size", str(BATCH_SIZES["hybrid"]["default"])],
        },
    ]
    return jobs


def clear_gpu():
    """GPU 메모리 완전 초기화"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def run_job(job, log_file):
    """단일 학습 작업 실행 (OOM 시 배치 크기 절반으로 재시도)"""
    name = job["name"]
    module = job["module"]
    args = job["args"]

    msg = f"\n{'='*60}\n🚀 [{name}] 시작 — {datetime.now().strftime('%H:%M:%S')}\n{'='*60}\n"
    print(msg, flush=True)
    log_file.write(msg)
    log_file.flush()

    # GPU 메모리 초기화
    clear_gpu()

    start = time.time()
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            # sys.argv를 조작하여 각 스크립트의 argparse가 올바르게 동작하도록 함
            original_argv = sys.argv
            sys.argv = [module] + args
            
            # 모듈을 직접 import하고 실행
            if "train_cnn14" in module:
                from ai.scripts.audio.train_cnn14 import train as train_cnn14
                # args에서 값 추출
                mode = args[args.index("--mode") + 1]
                epochs = int(args[args.index("--epochs") + 1])
                batch_size = int(args[args.index("--batch_size") + 1])
                train_cnn14(mode, epochs, batch_size)

            elif "train_ast" in module:
                from ai.scripts.audio.train_ast import train as train_ast
                mode = args[args.index("--mode") + 1]
                epochs = int(args[args.index("--epochs") + 1])
                batch_size = int(args[args.index("--batch_size") + 1])
                train_ast(mode, epochs, batch_size)

            elif "train_passt" in module:
                from ai.scripts.audio.train_passt import train as train_passt
                arch = args[args.index("--arch") + 1]
                mode = args[args.index("--mode") + 1]
                epochs = int(args[args.index("--epochs") + 1])
                batch_size = int(args[args.index("--batch_size") + 1])
                train_passt(arch, mode, epochs, batch_size)

            elif "train_hybrid" in module:
                from ai.scripts.audio.train_hybrid import train as train_hybrid
                teacher = args[args.index("--teacher") + 1]
                epochs = int(args[args.index("--epochs") + 1])
                batch_size = int(args[args.index("--batch_size") + 1])
                train_hybrid(teacher, epochs, batch_size)

            sys.argv = original_argv
            
            elapsed = time.time() - start
            elapsed_str = str(timedelta(seconds=int(elapsed)))
            msg = f"✅ [{name}] 완료 — 소요: {elapsed_str}\n"
            print(msg, flush=True)
            log_file.write(msg)
            log_file.flush()
            return True

        except torch.cuda.OutOfMemoryError:
            clear_gpu()
            sys.argv = original_argv
            
            if attempt < max_retries:
                # 배치 크기 절반으로 줄여서 재시도
                bs_idx = args.index("--batch_size") + 1
                old_bs = int(args[bs_idx])
                new_bs = max(2, old_bs // 2)
                args[bs_idx] = str(new_bs)
                msg = f"⚠️  [{name}] OOM! 배치 크기 {old_bs} → {new_bs}로 재시도 ({attempt+1}/{max_retries})\n"
                print(msg, flush=True)
                log_file.write(msg)
                log_file.flush()
            else:
                msg = f"❌ [{name}] OOM 해결 불가 (최소 배치에서도 실패). 건너뜀.\n"
                print(msg, flush=True)
                log_file.write(msg)
                log_file.flush()
                return False

        except Exception as e:
            sys.argv = original_argv
            clear_gpu()
            tb = traceback.format_exc()
            msg = f"❌ [{name}] 에러 발생:\n{tb}\n"
            print(msg, flush=True)
            log_file.write(msg)
            log_file.flush()
            return False

    return False


def main():
    parser = argparse.ArgumentParser(description="전체 벤치마크 자동 실행")
    parser.add_argument("--dry-run", action="store_true", help="1 epoch만 실행하여 오류 확인")
    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        os.environ["BENCHMARK_DRY_RUN"] = "1"
    else:
        os.environ.pop("BENCHMARK_DRY_RUN", None)
    jobs = get_jobs(dry_run)

    mode_str = "🧪 DRY-RUN (1 epoch)" if dry_run else "🚀 FULL BENCHMARK"
    log_path = os.path.join("ai", "runs", "benchmark_log.txt")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    total_start = time.time()

    with open(log_path, "a", encoding="utf-8") as log_file:
        banner = f"""
{'='*60}
{mode_str}
시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}
VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB
총 작업: {len(jobs)}개
{'='*60}
"""
        print(banner, flush=True)
        log_file.write(banner)
        log_file.flush()

        results = {}
        for i, job in enumerate(jobs):
            print(f"\n📋 진행: [{i+1}/{len(jobs)}] {job['name']}", flush=True)
            success = run_job(job, log_file)
            results[job["name"]] = "✅" if success else "❌"
            clear_gpu()

        # ── 최종 요약 ──
        total_elapsed = str(timedelta(seconds=int(time.time() - total_start)))
        summary = f"""
{'='*60}
📊 벤치마크 완료 — 총 소요: {total_elapsed}
{'='*60}
"""
        for name, status in results.items():
            summary += f"  {status} {name}\n"

        summary += f"{'='*60}\n"
        print(summary, flush=True)
        log_file.write(summary)
        log_file.flush()

    # ── 결과표 출력 ──
    print("\n📊 결과표 출력 중...\n", flush=True)
    from ai.scripts.audio.benchmark_all import load_all_metrics, print_table
    print_table(load_all_metrics())


if __name__ == "__main__":
    main()

# 1️⃣ 배치 크기 & 메모리

# run_all_benchmarks.py에서 각 모델별로 배치 크기를 GPU VRAM 기준으로 안전하게 지정해놨습니다.

# RTX 3050 6GB 기준이라 학원 컴퓨터 VRAM이 충분하다면 그대로 쓰면 되고, 부족하면 스크립트가 자동으로 배치를 절반으로 줄여 재시도합니다.

# 따라서 OOM 때문에 학습이 중단될 가능성도 최소화되어 있습니다.

# 2️⃣ 데이터 처리

# 데이터셋은 group-level stratified split + augmentation을 사용하므로, RunPod이든 학원 PC든 **동일한 랜덤 시드(42)**로 처리됩니다.

# 즉, train/val/test split과 augmentation 결과는 재현 가능 → 성능 수치 차이 거의 없음

# 3️⃣ GPU vs CPU 차이

# 학원 PC에 GPU가 있다면 GPU로 학습 → 런팟과 속도 차이만 존재

# CPU만으로 돌리면 매우 느리지만 결과 자체는 동일

# latency나 runtime 지표만 달라질 뿐, F1, Accuracy, Balanced Accuracy 등 성능 지표는 동일

# 4️⃣ 기타

# --dry-run 옵션 없이 그냥 돌리면 full epochs로 학습

# 스크립트가 각 모델별로 try/except, OOM 처리, GPU cache 초기화까지 지원 → 장시간 돌려도 안정적

# 로그는 ai/runs/benchmark_log.txt에 계속 기록 → 중간 상황 확인 가능

# 💡 정리

# 학원 컴에서 켜두고 학습해도 런팟과 동일한 모델 성능이 나옵니다.

# 다만, 학원 컴 GPU 사양에 따라 학습 시간은 더 길어질 수 있음.

# 안전하게 오래 걸려도 상관없다면 그냥 돌려도 문제없어요.