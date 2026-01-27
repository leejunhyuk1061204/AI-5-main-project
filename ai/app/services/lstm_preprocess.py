# ai/app/services/lstm_preprocess.py (추가/수정)

from typing import Any

def load_schema(schema_path: str) -> List[str]:
    with open(schema_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    # schema를 {"features":[...]}로 저장해도 되고, 그냥 리스트로 저장해도 됨
    return obj["features"] if isinstance(obj, dict) else obj

def load_scaler(scaler_path: str) -> Dict[str, Any]:
    with open(scaler_path, "r", encoding="utf-8") as f:
        return json.load(f)

def align_features(features: Dict[str, Any], schema: List[str]) -> Tuple[np.ndarray, List[str]]:
    """schema 순서대로 벡터 만들기. 없는 feature는 NaN으로 두고 나중에 결측 처리"""
    vec = np.full((len(schema),), np.nan, dtype=np.float32)
    missing = []
    for i, name in enumerate(schema):
        if name in features and features[name] is not None:
            try:
                vec[i] = float(features[name])
            except:
                vec[i] = np.nan
        else:
            missing.append(name)
    return vec, missing

def resample_to_grid(records: List[Dict[str, Any]], schema: List[str],
                     duration_sec: int, sampling_hz: float, timestamp_unit: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    records: [{"t":0, "features":{...}}, ...]
    return: (T, F) with fixed grid length
    """
    T = int(duration_sec * sampling_hz)
    # grid time in seconds
    dt = 1.0 / sampling_hz
    grid = np.arange(T, dtype=np.float32) * dt  # 0, dt, 2dt ...

    # parse time
    ts = []
    vecs = []
    missing_any = set()
    for r in records:
        t = float(r.get("t", np.nan))
        if timestamp_unit == "ms":
            t = t / 1000.0
        # s이면 그대로
        feats = r.get("features", {}) or {}
        vec, missing = align_features(feats, schema)
        ts.append(t)
        vecs.append(vec)
        for m in missing:
            missing_any.add(m)

    ts = np.array(ts, dtype=np.float32)
    X = np.stack(vecs, axis=0)  # (Nrec, F)

    # sort by time, drop nan t
    valid = ~np.isnan(ts)
    ts = ts[valid]
    X = X[valid]
    order = np.argsort(ts)
    ts = ts[order]
    X = X[order]

    received_points = int(len(ts))
    expected_points = T
    coverage = float(received_points / expected_points) if expected_points > 0 else 0.0

    # map each record to nearest grid index (simple + robust)
    grid_idx = np.clip(np.round(ts / dt).astype(int), 0, T-1)

    out = np.full((T, len(schema)), np.nan, dtype=np.float32)
    # if duplicates: last write wins
    for i, gi in enumerate(grid_idx):
        out[gi] = X[i]

    # fill missing over time (infer-safe: ffill only)
    df = pd.DataFrame(out, columns=schema)
    df = df.ffill()  # 미래값 안 씀
    out = df.to_numpy(dtype=np.float32)

    dq = {
        "expected_points": expected_points,
        "received_points": received_points,
        "coverage": round(coverage, 4),
        "missing_features": sorted(list(missing_any)),
    }
    return out, dq

def apply_scaler(X_tf: np.ndarray, scaler: Dict[str, Any], schema: List[str]) -> np.ndarray:
    """
    X_tf: (T,F)
    scaler signals 순서와 schema 순서가 동일하다는 전제(이게 schema-driven의 핵심)
    """
    if scaler.get("type") != "zscore":
        raise ValueError("Unsupported scaler")
    if scaler.get("signals") != schema:
        # 실무 방어 포인트: 신호 순서 불일치 방지
        raise ValueError("Scaler schema mismatch")

    mean = np.array(scaler["mean"], dtype=np.float32)
    std  = np.array(scaler["std"], dtype=np.float32)
    std = np.where(std < 1e-8, 1.0, std)
    return (X_tf - mean) / std

def preprocess_anomaly_request(req: Dict[str, Any],
                               schema_path: str,
                               scaler_path: str) -> Tuple[np.ndarray, Dict[str, Any], List[str]]:
    schema = load_schema(schema_path)
    scaler = load_scaler(scaler_path)

    duration_sec = int(req.get("duration_sec", 60))
    sampling_hz = float(req.get("sampling_hz", 1))
    timestamp_unit = req.get("timestamp_unit", "s")
    records = req.get("data", []) or []

    X_tf, dq = resample_to_grid(records, schema, duration_sec, sampling_hz, timestamp_unit)
    X_tf = apply_scaler(X_tf, scaler, schema)

    # model input: (1,T,F)
    X = X_tf[None, ...].astype(np.float32)
    return X, dq, schema
