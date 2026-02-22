# ai/scripts/audio/advanced_metrics.py
import numpy as np
from sklearn.metrics import roc_curve
import torch

def calculate_fpr_at_recall(y_true, y_scores, target_recalls=[0.99, 0.995, 0.997]):
    """
    Computes the False Positive Rate (FPR) at specific True Positive Rate (Recall) targets.
    """
    if len(np.unique(y_true)) < 2:
        return {f"fpr_at_p{int(r*1000)/10}": 0.0 for r in target_recalls}

    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    
    results = {}
    for target in target_recalls:
        # Find the first index where TPR >= target
        idx = np.where(tpr >= target)[0]
        if len(idx) > 0:
            val = fpr[idx[0]]
        else:
            val = 1.0
        results[f"fpr_at_p{int(target*1000)/10}"] = float(val)
    
    return results

def calculate_trr(y_scores_normal):
    """
    Tail Response Ratio (TRR): Measure the 'heaviness' of the tail in normal score distribution.
    A thicker tail means more likely false alarms in production.
    """
    if len(y_scores_normal) == 0:
        return 0.0
    
    mean_val = np.mean(y_scores_normal)
    std_val = np.std(y_scores_normal)
    
    if std_val == 0:
        return 0.0
        
    # Threshold at Mean + 2 Sigma (Standard outlier threshold)
    threshold = mean_val + 2 * std_val
    tail_count = np.sum(y_scores_normal > threshold)
    trr = tail_count / len(y_scores_normal)
    
    return float(trr)

def calculate_nrs(embeddings_normal):
    """
    Normalized Embedding Stability (NRS):
    Measures how tightly clustered the normal samples are in embedding space.
    Higher values indicate more distinct 'normality'.
    """
    if len(embeddings_normal) < 2:
        return 0.0
    
    # Standardize embeddings
    norms = np.linalg.norm(embeddings_normal, axis=1, keepdims=True)
    norm_embeddings = embeddings_normal / (norms + 1e-9)
    
    centroid = np.mean(norm_embeddings, axis=0)
    centroid = centroid / (np.linalg.norm(centroid) + 1e-9)
    
    # Cosine similarities to centroid
    similarities = np.dot(norm_embeddings, centroid)
    
    # NRS is the average similarity (higher = more stable/clustered)
    nrs = np.mean(similarities)
    return float(nrs)

def calculate_divergence(train_feats, test_feats):
    """
    Train-Test Divergence:
    Euclidean distance between the means of train and test features (Normal only).
    Measures potential distribution shift.
    """
    if len(train_feats) == 0 or len(test_feats) == 0:
        return 0.0
    
    train_mean = np.mean(train_feats, axis=0)
    test_mean = np.mean(test_feats, axis=0)
    
    # Euclidean distance between means
    dist = np.linalg.norm(train_mean - test_mean)
    
    # Normalize by the average norm of train features to make it scale-invariant
    train_norm = np.mean(np.linalg.norm(train_feats, axis=1))
    if train_norm > 0:
        dist /= train_norm
        
    return float(dist)
