import argparse
import json
import pathlib
import pandas as pd


def to_jsonl(
    input_csv: str,
    output_path: str,
    dataset_id: str,
    label_col: str,
    channels: list,
    sampling_hz: int,
    window_sec: int,
    stride_sec: int,
):
    df = pd.read_csv(input_csv)

    missing = set(channels + [label_col]) - set(df.columns)
    if missing:
        raise AssertionError(f"Missing columns: {missing}")

    df = df.dropna(subset=[label_col] + channels)

    labels = df[label_col].tolist()
    data = {col: df[col].tolist() for col in channels}
    duration_sec = int(len(df) / sampling_hz)

    item = {
        "dataset_id": dataset_id,
        "trip_id": f"{dataset_id}_labeled_001",
        "sampling_hz": sampling_hz,
        "duration_sec": duration_sec,
        "window_sec": window_sec,
        "stride_sec": stride_sec,
        "channels": channels,
        "data": data,
        "labels": labels,
        "meta": {
            "label_col": label_col,
            "label_values": sorted(pd.Series(labels).unique().tolist()),
        },
    }

    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(item) + "\n")

    print(
        f"[OK] JSONL saved -> {output_path}\n"
        f"   rows_total={len(df)} | duration_sec={duration_sec}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dataset_id", required=True)
    parser.add_argument("--label_col", required=True)
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
        channels=args.channels,
        sampling_hz=args.sampling_hz,
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
    )
