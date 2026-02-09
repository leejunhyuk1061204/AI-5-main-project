# ai/scripts/build_lstm_dataset.py
from ai.app.services.lstm_preprocess import build_lstm_ae_dataset, PreprocessConfig


def main():
    raw_dir = "ai/data/obd/raw/normal"
    out_dir = "ai/data/processed/lstm_ae"

    signals = [
        "engine_coolant_temp_c",
        "imap_kpa",
        "engine_rpm",
        "vehicle_speed_kmh",
        "intake_air_temp_c",
        "maf_gps",
        "throttle_pos_pct",
        "ambient_air_temp_c",
        "acc_pedal_pos_d_pct",
        "acc_pedal_pos_e_pct",
    ]

    cfg = PreprocessConfig(
        sampling_hz=10.0,
        window_sec=60,
        stride_sec=20,
        timestamp_col="timestamp",
        timestamp_format="%H:%M:%S.%f",
        fill_method="ffill",
        normalize="zscore",
        min_coverage=0.9,
        resample="none",
        rename_map={
            "Time": "timestamp",
            "Engine Coolant Temperature [Â°C]": "engine_coolant_temp_c",
            "Intake Manifold Absolute Pressure [kPa]": "imap_kpa",
            "Engine RPM [RPM]": "engine_rpm",
            "Vehicle Speed Sensor [km/h]": "vehicle_speed_kmh",
            "Intake Air Temperature [Â°C]": "intake_air_temp_c",
            "Air Flow Rate from Mass Flow Sensor [g/s]": "maf_gps",
            "Absolute Throttle Position [%]": "throttle_pos_pct",
            "Ambient Air Temperature [Â°C]": "ambient_air_temp_c",
            "Accelerator Pedal Position D [%]": "acc_pedal_pos_d_pct",
            "Accelerator Pedal Position E [%]": "acc_pedal_pos_e_pct",
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
