import torch
import os

def get_head_norm(path):
    print(f"Loading {path}...")
    try:
        print(f"Loading state dict for {path}...")
        sd = torch.load(path, map_location='cpu', weights_only=True)
        print(f"Loaded {path}")
        
        results = {}
        target_keys = ['type_head.weight', 'abnormal_head.weight', 'binary_head.weight', 'fusion.type_head.weight', 'fusion.binary_head.weight']
        
        for k in sd.keys():
            for tk in target_keys:
                if tk in k:
                    results[k] = torch.norm(sd[k].float()).item()
        
        return results
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    baseline_path = "ai/runs/cnn14_baseline/best_model.pt"
    finetune_path = "ai/runs/cnn14_finetune/best_model.pt"
    
    b_norms = get_head_norm(baseline_path)
    f_norms = get_head_norm(finetune_path)
    
    print("\n--- Comparison Table ---")
    print(f"{'Parameter':<30} | {'Baseline':<12} | {'Finetune':<12} | {'Diff':<12}")
    print("-" * 75)
    
    all_keys = sorted(set(list(b_norms.keys()) + list(f_norms.keys())))
    for k in all_keys:
        b_val = b_norms.get(k, 0.0)
        f_val = f_norms.get(k, 0.0)
        diff = f_val - b_val
        print(f"{k:<30} | {b_val:<12.6f} | {f_val:<12.6f} | {diff:<12.6f}")
