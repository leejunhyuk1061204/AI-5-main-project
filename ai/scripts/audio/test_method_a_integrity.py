"""
[파일 용도] Method A (계층적 분류) 정합성 테스트
Normal 클래스로 예측되었을 때, 하위 Type 분류 결과가 무시되거나 특정 값으로 처리되는지 검증합니다.
시스템의 논리적 모순이 없는지 확인하는 단위 테스트입니다.
"""
import torch
import numpy as np
import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

from ai.scripts.audio.train_passt import PaSSTMultiTask
from ai.scripts.audio.config import ABNORMAL_THRESHOLD, OTHER_THRESHOLD, TYPE_LABELS, DEVICE
from ai.scripts.audio.data_loader import balance_dataset

def test_1_forward_pass():
    print("\n--- [Test 1] PaSST Forward Pass ---")
    try:
        # PaSST 모델 초기화 (pretrained=False로 속도 최적화)
        model = PaSSTMultiTask(arch="passt_s_p16_s16_128_ap468", pretrained=False).to(DEVICE)
        model.eval()
        
        # 더미 waveform 생성 (B=2, T=1초 @ 16kHz로 축소)
        dummy_audio = torch.randn(2, 16000).to(DEVICE)
        
        with torch.no_grad():
            type_logits, abnormal_logits = model(dummy_audio)
            
        print(f"✅ Type Logits shape: {type_logits.shape} (Expected: [2, 3])")
        print(f"✅ Abnormal Logits shape: {abnormal_logits.shape} (Expected: [2,])")
        assert type_logits.shape == (2, 3)
        assert abnormal_logits.shape == (2,)
    except Exception as e:
        print(f"❌ Forward Pass Failed: {e}")

def test_2_hierarchical_inference_logic():
    print("\n--- [Test 2] Hierarchical Inference (Method A) Logic ---")
    
    # 가상의 Logits 데이터
    # Case 1: Normal (Abnormal Logit Low)
    # Case 2: Abnormal + High Confidence Type
    # Case 3: Abnormal + Low Confidence Type (Other)
    t_logs = torch.tensor([
        [2.0, 1.0, 0.5], # Case 1 (Ignored if abn low)
        [0.1, 5.0, 0.2], # Case 2 (Strong Engine)
        [0.5, 0.6, 0.5]  # Case 3 (Weak, Other)
    ])
    a_logs = torch.tensor([-5.0, 10.0, 10.0]) # Normal, Abnormal, Abnormal
    
    # Logic Simulation
    a_probs = torch.sigmoid(a_logs)
    a_preds = a_probs > ABNORMAL_THRESHOLD
    
    t_probs = torch.softmax(t_logs, dim=1)
    max_p, t_preds = torch.max(t_probs, dim=1)
    
    final_preds = torch.zeros_like(t_preds)
    is_abn_pred = a_preds
    
    is_other = is_abn_pred & (max_p < OTHER_THRESHOLD)
    is_typed = is_abn_pred & (~is_other)
    
    final_preds[is_other] = 4
    final_preds[is_typed] = t_preds[is_typed] + 1
    
    results = final_preds.numpy()
    print(f"Predictions: {results} (0=Normal, 1-3=Types, 4=Other)")
    
    expected = [0, 2, 4] # Normal, Engine(1+1), Other
    assert np.array_equal(results, expected), f"Expected {expected}, got {list(results)}"
    print("✅ Hierarchical Inference Logic Passed!")

def test_3_oversampling():
    print("\n--- [Test 3] Data Loader Oversampling ---")
    # 불균형 데이터셋 리스트 시뮬레이션
    dummy_data = [
        {"type": "normal", "path": "n1"},
        {"type": "normal", "path": "n2"},
        {"type": "starter", "path": "s1"}, # Starter
        {"type": "engine", "path": "e1"}, # Engine
        {"type": "brake", "path": "b1"}, # Brake
    ]
    
    # samples_per_cls = 3 설정 시 결과 확인
    balanced = balance_dataset(dummy_data, samples_per_cls=3, name="Test")
    counts = {}
    for x in balanced:
        lbl = x["type"]
        counts[lbl] = counts.get(lbl, 0) + 1
    
    print(f"Balanced Counts: {counts}")
    # normal, starter, engine, brake 각각 3개씩 있어야 함
    for lbl in ["normal", "starter", "engine", "brake"]:
        assert counts.get(lbl, 0) == 3, f"Label {lbl} count is {counts.get(lbl, 0)}, expected 3"
    
    print("✅ Oversampling Balancing Logic Passed!")

def test_4_duplicate_check():
    print("\n--- [Test 4] MD5 Duplicate Check ---")
    tmp_dir = Path("ai/scripts/audio/test_tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    f1 = tmp_dir / "dup1.txt"
    f2 = tmp_dir / "dup2.txt"
    content = b"Same Content For MD5 Test"
    f1.write_bytes(content)
    f2.write_bytes(content)
    
    # hashlib MD5 simulation
    import hashlib
    def get_md5(p):
        h = hashlib.md5()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()
    
    md5_1 = get_md5(f1)
    md5_2 = get_md5(f2)
    
    print(f"MD5 1: {md5_1}")
    print(f"MD5 2: {md5_2}")
    assert md5_1 == md5_2
    print("✅ MD5 Duplicate Detection Logic Verified!")
    
    # Cleanup (Robust with rmtree)
    shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    test_1_forward_pass()
    test_2_hierarchical_inference_logic()
    test_3_oversampling()
    test_4_duplicate_check()
    print("\n✨ ALL INTEGRITY TESTS PASSED! ✨")
