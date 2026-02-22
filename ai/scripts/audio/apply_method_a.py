
"""
[파일 용도] Method A (계층적 분류) 적용 로직
이 스크립트는 모델의 출력(로짓)이나 메타데이터에 Method A(계층적 분류) 규칙을 적용하거나 검증하는 역할을 합니다.
Normal 판정 시 하위 Type 분류를 무시하는 등의 후처리 로직을 포함할 수 있습니다.
"""
import os
import re

def patch_file(filepath, patterns_and_replacements):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for pattern, replacement in patterns_and_replacements:
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Patched {filepath}")

# 1. create_dataloaders unpack fix (Universal for v3.1 - 6 items)
# Replace ANY existing create_dataloaders unpack line with the 6-item version
UNPACK_PATTERN = r'[a-zA-Z0-9_, ]+\s*=\s*create_dataloaders\([^)]*\)'

# 2. COMPARISON LOGIC (Universal)
COMPARISON_LOGIC_BLOCK = """
    # ── [V3.1] Dual Evaluation Strategy — Comparative Report ──
    print(f"\\n{'='*80}", flush=True)
    print(f"🏁 DUAL TEST EVALUATION — Original vs Balanced Subset", flush=True)
    print(f"{'='*80}", flush=True)

    # 1. Original Distribution Test
    test_metrics = evaluate_model(model, test_loader, {eval_args_desc_orig})
    
    # 2. Balanced Subset Evaluation (Fair Comparison)
    balanced_metrics = evaluate_model(model, test_loader_balanced, {eval_args_desc_bal})

    print(f"\\n📊 COMPARATIVE PERFORMANCE REPORT (Test Set)", flush=True)
    print(f"{'-'*80}", flush=True)
    print(f"{'Metric':<25} | {'Original Dist':<15} | {'Balanced Subset':<15} | {'Diff':<10}", flush=True)
    print(f"{'-'*80}", flush=True)
    
    metrics_to_comp = [
        ("Accuracy", "type_acc"),
        ("Balanced Acc", "type_balanced_acc"),
        ("Macro F1", "type_macro_f1"),
        ("Starter F1", "starter_f1"),
        ("Engine F1", "engine_f1"),
        ("Brake F1", "brake_f1"),
    ]
    
    for label, key in metrics_to_comp:
        orig = test_metrics.get(key, 0)
        bal = balanced_metrics.get(key, 0)
        diff = bal - orig
        diff_str = f"{diff:+.4f}" if abs(diff) > 1e-6 else "0.0000"
        print(f"{label:<25} | {orig:<15.4f} | {bal:<15.4f} | {diff_str:<10}", flush=True)
    print(f"{'='*80}\\n", flush=True)
"""

def patch_universal(path, model_id, eval_prefix=""):
    if eval_prefix:
        eval_prefix += ", "
    
    logic = COMPARISON_LOGIC_BLOCK.format(
        eval_args_desc_orig=f'{eval_prefix}desc="FINAL TEST (ORIGINAL)"', 
        eval_args_desc_bal=f'{eval_prefix}desc="FINAL TEST (BALANCED SUBSET)"'
    )
    
    # 6-item unpack replacement
    if "hybrid" in path:
        unpack_repl = 'train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders(arch_for_loader, feature_extractor=fe, batch_size=batch_size)'
    elif "ast" in path:
        unpack_repl = 'train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders("ast", feature_extractor=fe, batch_size=batch_size)'
    elif "cnn14" in path:
        unpack_repl = 'train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders("cnn", batch_size=batch_size)'
    else: # passt
        unpack_repl = 'train_loader, val_loader, val_loader_balanced, test_loader, test_loader_balanced, type_weights = create_dataloaders("passt", batch_size=batch_size)'

    replacements = [(UNPACK_PATTERN, unpack_repl)]
    
    # Patch for final test section
    if "ast" in path:
        pattern = r'(# ── (Test|FINAL TEST).*?)(if __name__ == "__main__":|return )'
        # AST specific metrics field
        ext_fields = '"balanced_type_macro_f1": balanced_metrics["type_macro_f1"], "balanced_type_acc": balanced_metrics["type_acc"], '
        repl_body = f"""# ── Test ──
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
    model = model.to(DEVICE)
    {logic}
    # Latency calculation
    dummy = torch.randn(1, 1024, 128).to(DEVICE)
    latency = measure_latency(model, dummy, DEVICE)
    model_size = os.path.getsize(best_path) / (1024**2) if os.path.exists(best_path) else 0
    final = {{"model": "ast", "mode": mode, **test_metrics, {ext_fields} "latency_ms": round(latency, 1), "model_size_mb": round(model_size, 1)}}
    save_metrics("ast", mode, final)
    print(f"\\n✅ AST {{mode.upper()}} complete!\\n", flush=True)
    return final
"""
        replacements.append((pattern, repl_body))
        
    elif "cnn14" in path:
        pattern = r'(# ── (Test Evaluation|FINAL TEST EVALUATION|Test|FINAL TEST) ──.*?)(if __name__ == "__main__":|return )'
        ext_fields = '"balanced_type_macro_f1": balanced_metrics["type_macro_f1"], "balanced_type_acc": balanced_metrics["type_acc"], '
        repl_body = f"""# ── Test Evaluation ──
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=True))
    model = model.to(DEVICE)
    {logic}
    # Latency measurement
    dummy_mel = torch.randn(1, 128, 501).to(DEVICE)
    latency = measure_latency(model, dummy_mel, DEVICE)
    model_size_mb = os.path.getsize(best_path) / (1024 * 1024) if os.path.exists(best_path) else 0
    final_metrics = {{"model": "cnn14", "mode": mode, **test_metrics, {ext_fields} "latency_ms": round(latency, 1), "model_size_mb": round(model_size_mb, 1)}}
    save_metrics("cnn14", mode, final_metrics)
    print(f"\\n✅ CNN14 {{mode.upper()}} training complete!\\n", flush=True)
    return final_metrics
"""
        replacements.append((pattern, repl_body))

    elif "passt" in path:
        pattern = r'(# ── (Test Elevation|FINAL TEST EVALUATION|Test Evaluation|Test|FINAL TEST) ──.*?)(if __name__ == "__main__":|return )'
        ext_fields = '"balanced_type_macro_f1": balanced_metrics["type_macro_f1"], "balanced_type_acc": balanced_metrics["type_acc"], '
        # [Fix] dummy shape for PaSST (B, T) - 2D is safer to avoid squeeze issues
        repl_body = f"""# ── Test Evaluation ──
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
    model = model.to(DEVICE)
    {logic}
    # Latency measurement
    dummy = torch.randn(1, 16000 * 5).to(DEVICE) 
    latency = measure_latency(model, dummy, DEVICE)
    model_size_mb = os.path.getsize(best_path) / (1024 * 1024) if os.path.exists(best_path) else 0
    final_metrics = {{"model": "passt", "mode": mode, **test_metrics, {ext_fields} "latency_ms": round(latency, 1), "model_size_mb": round(model_size_mb, 1)}}
    save_metrics("passt", mode, final_metrics)
    print(f"\\n✅ PaSST {{mode.upper()}} training complete!\\n", flush=True)
    return final_metrics
"""
        replacements.append((pattern, repl_body))

    elif "hybrid" in path:
        pattern = r'(# ── (Test Elevation|FINAL TEST EVALUATION|Test Evaluation|Test|FINAL TEST) ──.*?)(if __name__ == "__main__":|# ── Latency ──)'
        # Hybrid is complex, replace up to returns
        ext_fields = '"balanced_type_macro_f1": balanced_metrics["type_macro_f1"], "balanced_type_acc": balanced_metrics["type_acc"], '
        repl_body = f"""# ── Test Evaluation ──
    best_path = os.path.join(save_dir, "best_model.pt")
    if os.path.exists(best_path):
        model.load_state_dict(torch.load(best_path, map_location=DEVICE, weights_only=False))
    model = model.to(DEVICE)
    {logic}
    # ── Latency 측정 ──
    print(f"⚡ Measuring latency...", flush=True)
    dummy_mel = torch.randn(1, 128, 501).to(DEVICE)
    dummy_ast = torch.randn(1, 1024, 128).to(DEVICE) if teacher == "ast" else None
    dummy_raw = torch.randn(1, 16000 * 5).to(DEVICE)
    class LatencyWrapper(torch.nn.Module):
        def __init__(self, m, t, mel, ast, raw):
            super().__init__()
            self.m, self.t, self.mel, self.ast, self.raw = m, t, mel, ast, raw
        def forward(self, x):
            return self.m(mel_input=self.mel, ast_input=self.ast if self.t=="ast" else None, raw_audio=self.raw)
    wrapper = LatencyWrapper(model, teacher, dummy_mel, dummy_ast, dummy_raw)
    latency = measure_latency(wrapper, torch.zeros(1).to(DEVICE), DEVICE)
    model_size = os.path.getsize(best_path) / (1024**2) if os.path.exists(best_path) else 0
    final = {{"model": model_name, "mode": "hybrid", **test_metrics, {ext_fields} "latency_ms": round(latency, 1), "model_size_mb": round(model_size, 1)}}
    save_metrics(model_name, "hybrid", final)
    print(f"\\n✅ Hybrid [{{teacher_short}}+CNN14] complete!\\n", flush=True)
    return final
"""
        # For hybrid, match the whole block since it overlaps with latency
        pattern_hybrid = r'# ── Test ──.*?save_metrics\(model_name, "hybrid", final\)'
        replacements.append((pattern_hybrid, repl_body))

    patch_file(path, replacements)

# Run all
patch_universal('ai/scripts/audio/train_ast.py', 'ast')
patch_universal('ai/scripts/audio/train_cnn14.py', 'cnn14')
patch_universal('ai/scripts/audio/train_passt.py', 'passt')
patch_universal('ai/scripts/audio/train_hybrid.py', 'hybrid', eval_prefix="teacher")

print("✨ All patches applied (v3.1 Dual Evaluation & Fixes)")
