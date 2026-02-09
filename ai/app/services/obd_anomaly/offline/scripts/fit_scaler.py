import json
import numpy as np
import joblib
from sklearn.preprocessing import MinMaxScaler
import pathlib

JSONL_PATH = "ai/app/services/obd_anomaly/offline/datasets/kaggle_efd/efd_full.jsonl"
SCALER_OUT = "ai/app/services/obd_anomaly/offline/registry/scalers/efd_minmax_v1.pkl"

def load_first_example(jsonl_path):
    with open(jsonl_path, "r", encoding="utf-8") as f:
        line = f.readline().strip()
        if not line:
            raise ValueError(f"No content in JSONL: {jsonl_path}")
        ex = json.loads(line)
    return ex

def build_matrix_from_example(ex):
    # channels를 JSONL에서 자동 추출
    channels = ex.get("channels", [])
    if not channels:
        raise ValueError("No 'channels' field in JSONL example.")

    data = ex.get("data", {})
    # 각 채널 길이 확인
    lengths = [len(data.get(ch, [])) for ch in channels]
    if any(l == 0 for l in lengths):
        raise ValueError(
            f"Some channels are empty. lengths={dict(zip(channels, lengths))}. "
            "Check prepare_kaggle.py filter (normal_value) and data availability."
        )

    # [T, C] 배열 생성
    X = np.stack([np.array(data[ch], dtype=float) for ch in channels], axis=1)
    return X, channels

if __name__ == "__main__":
    ex = load_first_example(JSONL_PATH)
    X, channels = build_matrix_from_example(ex)
    print(f"✅ Loaded JSONL: {JSONL_PATH}")
    print(f"   channels={channels}")
    print(f"   matrix shape={X.shape}  (T={X.shape[0]}, C={X.shape[1]})")

    scaler = MinMaxScaler()
    scaler.fit(X)

    pathlib.Path(SCALER_OUT).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, SCALER_OUT)
    print(f"✅ Scaler saved → {SCALER_OUT}")
