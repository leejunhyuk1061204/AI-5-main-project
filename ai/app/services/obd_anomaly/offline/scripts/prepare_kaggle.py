import argparse
import json
import pathlib
import pandas as pd


def to_jsonl(
    input_csv: str,
    output_path: str,
    dataset_id: str,
    label_col: str,
    normal_value,
    channels: list,
    sampling_hz: int,
    window_sec: int,
    stride_sec: int,
    fault_value=None,
    output_fault_path: str | None = None,
):
    # 1) CSV load
    df = pd.read_csv(input_csv)

    # 2) channel check
    missing = set(channels) - set(df.columns)
    if missing:
        raise AssertionError(f"Missing columns: {missing}")

    # 3) normalize label type
    nv = normal_value
    try:
        if pd.api.types.is_numeric_dtype(df[label_col]):
            nv = pd.to_numeric(normal_value)
        else:
            df[label_col] = df[label_col].astype(str).str.strip()
            nv = str(normal_value).strip()
    except Exception:
        nv = normal_value

    # 4) drop NaN
    df = df.dropna(subset=[label_col] + channels)

    # 5) normal filter
    is_normal = df[label_col] == nv
    df_normal = df[is_normal]

    if df_normal.empty:
        print(
            f"[WARN] No rows matched normal_value={nv} in column '{label_col}'. "
            f"(total={len(df)}, normals=0)"
        )

    # 6) JSONL (normal)
    data = {col: df_normal[col].tolist() for col in channels}
    duration_sec = int(len(df_normal) / sampling_hz)

    item = {
        "dataset_id": dataset_id,
        "trip_id": f"{dataset_id}_normal_001",
        "sampling_hz": sampling_hz,
        "duration_sec": duration_sec,
        "window_sec": window_sec,
        "stride_sec": stride_sec,
        "channels": channels,
        "data": data,
        "labels": ["normal"],
        "meta": {"label_col": label_col, "normal_value": str(nv)},
    }

    # 7) write normal
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(item) + "\n")

    print(
        f"[OK] JSONL saved -> {output_path}\n"
        f"   rows_total={len(df)} | rows_normal={len(df_normal)} | duration_sec={duration_sec}"
    )

    # 8) fault (optional)
    if fault_value is not None and output_fault_path:
        fv = fault_value
        try:
            if pd.api.types.is_numeric_dtype(df[label_col]):
                fv = pd.to_numeric(fault_value)
            else:
                fv = str(fault_value).strip()
        except Exception:
            fv = fault_value

        df_fault = df[df[label_col] == fv]
        if df_fault.empty:
            print(
                f"[WARN] No rows matched fault_value={fv} in column '{label_col}'. "
                f"(total={len(df)}, faults=0)"
            )
        else:
            fault_data = {col: df_fault[col].tolist() for col in channels}
            fault_duration_sec = int(len(df_fault) / sampling_hz)
            fault_item = {
                "dataset_id": dataset_id,
                "trip_id": f"{dataset_id}_fault_001",
                "sampling_hz": sampling_hz,
                "duration_sec": fault_duration_sec,
                "window_sec": window_sec,
                "stride_sec": stride_sec,
                "channels": channels,
                "data": fault_data,
                "labels": ["fault"],
                "meta": {"label_col": label_col, "fault_value": str(fv)},
            }
            pathlib.Path(output_fault_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_fault_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(fault_item) + "\n")
            print(
                f"[OK] JSONL saved -> {output_fault_path}\n"
                f"   rows_fault={len(df_fault)} | duration_sec={fault_duration_sec}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dataset_id", required=True)
    parser.add_argument("--label_col", required=True)
    parser.add_argument("--normal_value", required=True)
    parser.add_argument("--fault_value")
    parser.add_argument("--out_fault")
    parser.add_argument("--channels", nargs="+", required=True)
    parser.add_argument("--sampling_hz", type=int, required=True)
    parser.add_argument("--window_sec", type=int, required=True)
    parser.add_argument("--stride_sec", type=int, required=True)
    args = parser.parse_args()

    to_jsonl(
        input_csv=args.csv,
        output_path=args.out,
        dataset_id=args.dataset_id,
        label_col=args.label_col,
        normal_value=args.normal_value,
        channels=args.channels,
        sampling_hz=args.sampling_hz,
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
        fault_value=args.fault_value,
        output_fault_path=args.out_fault,
    )
