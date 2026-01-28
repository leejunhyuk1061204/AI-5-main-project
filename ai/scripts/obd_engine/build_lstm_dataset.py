# ai/scripts/build_lstm_dataset.py
from ai.app.services.lstm_preprocess import build_lstm_ae_dataset, PreprocessConfig


def main():
    raw_dir = "ai/data/obd/raw/normal"
    out_dir = "ai/data/processed/lstm_ae"

    signals = ["rpm", "speed", "coolant", "map"]

    cfg = PreprocessConfig(
        sampling_hz=10.0,
        window_sec=60,
        stride_sec=5,
        timestamp_col="timestamp",
        timestamp_format="%H:%M:%S.%f",  # Time이 HH:MM:SS.mmm 형태면 추천 (경고 줄어듦)
        fill_method="ffill_then_bfill",
        normalize="zscore",
        rename_map={
            "Time": "timestamp",
            "Engine RPM [RPM]": "rpm",
            "Vehicle Speed Sensor [km/h]": "speed",
            "Engine Coolant Temperature [°C]": "coolant",
            "Intake Manifold Absolute Pressure [kPa]": "map",
        },
    )

    train_npz, scaler_path, meta_path = build_lstm_ae_dataset(
        raw_dir=raw_dir,
        out_dir=out_dir,
        signals=signals,
        cfg=cfg,
    )

    print("[OK]")
    print("train_npz:", train_npz)
    print("scaler:", scaler_path)
    print("meta:", meta_path)


if __name__ == "__main__":
    main()
