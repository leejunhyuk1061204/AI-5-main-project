# ai/scripts/audio/test_source_leak.py
"""
🔍 통계적 소스 누수 테스트 (Statistical Source Leak Test) — Optimized

[목표]
단일 결과가 아닌 여러 Seed에서의 평균/분산을 통해 
정상(사이트) vs 비정상(유튜브) 데이터 간의 환경 차이(Leak)를 더 정확히 진단합니다.

[최적화]
- 모델 가중치: 1회만 로드 후 deepcopy (Seed별 디스크 I/O 제거)
- 데이터셋: 1회만 전처리 후 재사용 (pickle 캐시 + DataLoader 공유)
- 결과: 5 Seed 반복 시 기존 대비 5~10배 속도 개선

[통과 기준]
- 평균 Accuracy: 60~70%
- 최대 Accuracy: 80% 미만
"""
import os, copy, torch, torch.nn as nn
import numpy as np
from sklearn.metrics import accuracy_score

from ai.scripts.audio.config import (
    set_seed, DEVICE, COMMON_CONFIG
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
            preds = (torch.sigmoid(a_log) > 0.5).cpu().numpy().astype(int)
            val_preds.extend(preds)
            val_labels.extend(batch["abnormal_label"].numpy().astype(int))

    # 메모리 해제
    del local_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    acc = accuracy_score(val_labels, val_preds)
    return acc


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
    for i, seed in enumerate(seeds):
        print(f"🧪 [Experiment {i+1}/{len(seeds)}] Seed: {seed}...")
        acc = run_single_experiment_with_model(base_model, train_loader, val_loader, seed, epochs)
        results.append(acc)
        print(f"   -> Validation Accuracy: {acc:.4f}")

    # 기본 모델 메모리 해제
    del base_model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    results = np.array(results)
    mean_acc = np.mean(results)
    var_acc = np.var(results)
    max_acc = np.max(results)

    print(f"\n{'='*60}")
    print(f"📊 SUMMARY OF {len(seeds)} EXPERIMENTS")
    print(f"{'='*60}")
    print(f"Mean Accuracy: {mean_acc:.4f}")
    print(f"Variance:      {var_acc:.6f} (Std: {np.sqrt(var_acc):.4f})")
    print(f"Max Accuracy:  {max_acc:.4f}")
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
    run_statistical_leak_test(
        seeds=[42, 123, 777, 2024, 999],
        epochs=3
    )
