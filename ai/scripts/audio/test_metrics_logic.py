
import numpy as np
from ai.scripts.audio.advanced_metrics import calculate_fpr_at_recall, calculate_trr, calculate_nrs, calculate_divergence

def test_metrics():
    print("Testing Advanced Metrics...")
    
    # Dummy data
    y_true = np.array([0, 0, 0, 1, 1])
    y_scores = np.array([0.1, 0.2, 0.3, 0.9, 0.95])
    
    fpr_metrics = calculate_fpr_at_recall(y_true, y_scores)
    print(f"FPR Metrics: {fpr_metrics}")
    
    trr = calculate_trr(np.array([0.1, 0.2, 0.1, 0.5]))
    print(f"TRR: {trr}")
    
    nrs = calculate_nrs(np.random.rand(10, 512))
    print(f"NRS: {nrs}")
    
    div = calculate_divergence(np.random.rand(10, 512), np.random.rand(10, 512))
    print(f"Divergence: {div}")
    
    print("Test Complete!")

if __name__ == "__main__":
    test_metrics()
