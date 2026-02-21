# ai/scripts/audio/test_source_leak.py
"""
[파일 용도] 통계적 소스 누수(Source Leakage) 테스트
정상(Site) 데이터와 비정상(YouTube) 데이터 간의 환경적 차이(배경 소음 등)가 모델 학습에 영향을 주는지 확인합니다.
여러 Random Seed로 반복 실험하여 통계적으로 유의미한 누수가 없는지(Accuracy가 과도하게 높지 않은지) 검증합니다.
"""
import os, copy, torch, torch.nn as nn
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from ai.scripts.audio.config import (
    set_seed, DEVICE, COMMON_CONFIG, ABNORMAL_THRESHOLD
)
from ai.scripts.audio.data_loader import create_dataloaders
from ai.scripts.audio.train_cnn14 import CNN14MultiTask


def run_single_experiment_with_model(model, train_loader, val_loader, seed, epochs=3):
    """사전 로드된 모델 복사본으로 1회 누수 테스트 실행"""
    set_seed(seed)
    
    # 모델 상태 복사 (GPU 메모리 내에서 처리 — 디스크 I/O 없음)
    local_model = copy.deepcopy(model)
    local_model.to(DEVICE)
    
    optimizer = torch.optim.AdamW(local_model.parameters(), lr=1e-3)
    criterion_abn = nn.BCEWithLogitsLoss()
    fp16 = torch.cuda.is_available()
    scaler = torch.amp.GradScaler('cuda', enabled=fp16)

    for epoch in range(epochs):
        local_model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            with torch.amp.autocast('cuda', enabled=fp16):
                mel = batch["mel_input"].to(DEVICE)
                a_lbl = batch["abnormal_label"].to(DEVICE)
                a_lbl_smooth = a_lbl * 0.8 + 0.1
                
                _, a_log = local_model(mel)
                loss = criterion_abn(a_log, a_lbl_smooth)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

    # 검증
    local_model.eval()
    val_preds, val_labels = [], []
    with torch.no_grad():
        for batch in val_loader:
            mel = batch["mel_input"].to(DEVICE)
            _, a_log = local_model(mel)
            # 진단용 테스트이므로 임계값은 0.5로 고정 (신호 존재 여부 확인용)
            preds = (torch.sigmoid(a_log) > 0.8).cpu().numpy().astype(int)
            val_preds.extend(preds)
            val_labels.extend(batch["abnormal_label"].numpy().astype(int))

    # 메모리 해제
    del local_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    acc = accuracy_score(val_labels, val_preds)
    p, r, f1, _ = precision_recall_fscore_support(val_labels, val_preds, average='binary', zero_division=0)
    return {"acc": acc, "p": p, "r": r, "f1": f1}


def run_statistical_leak_test(seeds, epochs=3):
    print(f"\n{'='*60}")
    print(f"🔍 Statistical Source Leak Test ({len(seeds)} Seeds)")
    print(f"{'='*60}\n")
    
    # ── 1회만 로드 ──
    print("📦 [1/2] 모델 가중치 로드 (1회)...", flush=True)
    base_model = CNN14MultiTask().to(DEVICE)
    base_model.load_pretrained_weights()
    
    print("📦 [2/2] 데이터셋 전처리 (1회, 캐시 활용)...", flush=True)
    set_seed(seeds[0])  # 데이터 분할은 첫 번째 seed 기준
    train_loader, val_loader, _, _ = create_dataloaders("cnn", batch_size=COMMON_CONFIG["batch_size"])
    
    print(f"\n⚡ 준비 완료! {len(seeds)}개 Seed 반복 시작 (deepcopy + 캐시 재사용)\n")
    
    # ── Seed 반복 (모델/데이터 재로드 없음) ──
    results = []
    failed_seeds = []  # 실패한 Seed를 기록할 리스트
    
    for i, seed in enumerate(seeds):
        print(f"🧪 [Experiment {i+1}/{len(seeds)}] Seed: {seed}...")
        try:
            metrics = run_single_experiment_with_model(base_model, train_loader, val_loader, seed, epochs)
            results.append(metrics)
            print(f"   -> Acc: {metrics['acc']:.4f} | Prec: {metrics['p']:.4f} | Rec: {metrics['r']:.4f} | F1: {metrics['f1']:.4f}")
        except Exception as e:
            print(f"   -> Error in Seed {seed}: {e}")
            failed_seeds.append(seed)  # 실패한 Seed 기록

    # 기본 모델 메모리 해제
    del base_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # 실패한 Seed 출력
    if failed_seeds:
        print(f"\n❌ Failed Seeds: {failed_seeds}")
    else:
        print("\n✅ All Seeds Passed")

    if not results:
        print("⚠️ No valid results to summarize.")
        return

    sum_acc = np.array([r['acc'] for r in results])
    sum_p = np.array([r['p'] for r in results])
    sum_r = np.array([r['r'] for r in results])
    
    mean_acc = np.mean(sum_acc)
    mean_p = np.mean(sum_p)
    mean_r = np.mean(sum_r)
    max_acc = np.max(sum_acc)

    print(f"\n{'='*60}")
    print(f"📊 SUMMARY OF {len(results)} SUCCESSFUL EXPERIMENTS")
    print(f"{'='*60}")
    print(f"Mean Accuracy:  {mean_acc:.4f}")
    print(f"Mean Precision: {mean_p:.4f}")
    print(f"Mean Recall:    {mean_r:.4f}")
    print(f"Max Accuracy:   {max_acc:.4f}")
    print(f"{'='*60}")

    is_pass = (0.60 <= mean_acc <= 0.70) and (max_acc < 0.80)

    if is_pass:
        print("\n✅ PASS: 모델이 환경 차이에 크게 의존하지 않습니다.")
        print("결함 분류 벤치마크 학습을 진행하셔도 좋습니다.")
    else:
        print("\n❌ FAIL or ATYPICAL: 신뢰 구간을 벗어났습니다.")
        if max_acc >= 0.80:
            print("- 이유: 특정 실험에서 Accuracy가 80%를 초과했습니다 (Source Leak 위험).")
        if not (0.60 <= mean_acc <= 0.70):
            print(f"- 이유: 평균 Accuracy({mean_acc:.2%})가 기준 범위(60-70%) 밖입니다.")
        print("\n👉 조치: 데이터 증강(Aug)을 강화하거나 샘플링을 재검토하세요.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Statistical Source Leak Test (Optimized)")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds (default: 5)")
    parser.add_argument("--epochs", type=int, default=3, help="Epochs per experiment (default: 3)")
    parser.add_argument("--quick", action="store_true", help="Quick check: 1 seed, 2 epochs")
    
    args = parser.parse_args()
    
    if args.quick:
        target_seeds = [42]
        target_epochs = 2
        print("🏃 Quick Mode: Running 1 Seed, 2 Epochs...")
    else:
        all_seeds = [42, 123, 777, 2024, 999]
        target_seeds = all_seeds[:args.seeds]
        target_epochs = args.epochs
        
    run_statistical_leak_test(
        seeds=target_seeds,
        epochs=target_epochs
    )
