# Archived Audio Training Pipelines

## train_audio_clip.py
- Clip-level AST classification
- Used for early experiments with short (≈2s) audio clips
- Pros: simple, fast, good for small datasets
- Cons: not suitable for long-form inference

## train_audio_2stage.py
- Stage1: normal vs abnormal
- Stage2: fault type classification
- Pros: strong abnormal recall, interpretable
- Cons: complex, higher latency

## Reason for Archival
Current production system uses:
- 5s fixed window
- Sliding inference
- Temporal max aggregation

These scripts are kept for:
- ablation studies
- fallback strategies
- research reference