import pandas as pd

# CSV 로드
df = pd.read_csv("results/wear_factor_results.csv")

# category 추출 (frei / normal / stau)
df["category"] = df["file"].str.split("__").str[0]

print("\n=== 데이터 개수 ===")
print(df["category"].value_counts())

print("\n=== 평균 wear_factor (by category) ===")
print(df.groupby("category")["predicted_wear_factor"].mean())

print("\n=== 주행 특성 평균 (by category) ===")
print(
    df.groupby("category")[[
        "avg_rpm",
        "idle_ratio",
        "hard_accel_count",
        "hard_brake_count"
    ]].mean()
)

print("\n=== wear_factor 상관관계 ===")
print(
    df[[
        "predicted_wear_factor",
        "avg_rpm",
        "idle_ratio",
        "hard_accel_count",
        "hard_brake_count"
    ]].corr()
)
  