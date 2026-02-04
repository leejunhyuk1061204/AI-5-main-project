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
):
    # 1) CSV 로드
    df = pd.read_csv(input_csv)

    # 2) 채널 존재 검사
    missing = set(channels) - set(df.columns)
    if missing:
        raise AssertionError(f"Missing columns: {missing}")

    # 3) 라벨/정상값 타입 자동 정합
    nv = normal_value
    try:
        if pd.api.types.is_numeric_dtype(df[label_col]):
            nv = pd.to_numeric(normal_value)
        else:
            # 문자형이면 공백 제거/소문자 비교용 정규화
            df[label_col] = df[label_col].astype(str).str.strip()
            nv = str(normal_value).strip()
    except Exception:
        # 어떤 이유로든 검사 실패 시 원본 유지
        nv = normal_value

    # 4) NaN 제거(라벨/채널 결측치 드롭)
    df = df.dropna(subset=[label_col] + channels)

    # 5) 정상만 필터링
    is_normal = df[label_col] == nv
    df_normal = df[is_normal]

    if df_normal.empty:
        print(
            f"⚠️ No rows matched normal_value={nv} in column '{label_col}'. "
            f"(total={len(df)}, normals=0)"
        )

    # 6) JSONL 아이템 구성
    data = {col: df_normal[col].tolist() for col in channels}
    duration_sec = int(len(df_normal) / sampling_hz)

    item = {
        "dataset_id": dataset_id,
        "trip_id": f"{dataset_id}_001",
        "sampling_hz": sampling_hz,
        "duration_sec": duration_sec,
        "window_sec": window_sec,
        "stride_sec": stride_sec,
        "channels": channels,
        "data": data,
        "labels": [],  # 라벨이 필요하면 이후 확장
        "meta": {"label_col": label_col, "normal_value": str(nv)},
    }

    # 7) 출력 경로 생성 및 저장
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(item) + "\n")

    # 8) 로그
    print(
        f"✅ JSONL saved → {output_path}\n"
        f"   rows_total={len(df)} | rows_normal={len(df_normal)} | duration_sec={duration_sec}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dataset_id", required=True)
    parser.add_argument("--label_col", required=True)
    parser.add_argument("--normal_value", required=True)
    parser.add_argument("--channels", nargs="+", required=True)
    parser.add_argument("--sampling_hz", type=int, required=True)
    parser.add_argument("--window_sec", type=int, required=True)
    parser.add_argument("--stride_sec", type=int, required=True)
    args = parser.parse_args()

    # main에서 타입 정합을 위해 한 번 미리 로드/정규화할 수도 있었지만,
    # 함수 내부에서 처리하므로 바로 전달
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
    )
