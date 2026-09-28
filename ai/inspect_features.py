from pathlib import Path

from ai.data_loader import load_weather_data
from ai.feature_engineering import engineer_features


DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "era5_pune_test_clean.csv"
)


df = load_weather_data(DATA_PATH)
features = engineer_features(df)

print("\n=== DATASET ===")
print(f"Rows: {len(features)}")
print(f"Columns: {len(features.columns)}")

print("\n=== FEATURE COLUMNS ===")
for column in features.columns:
    print(f"- {column}")

print("\n=== FEATURE SUMMARY ===")
summary_columns = [
    "temperature_2m_c",
    "precipitation_mm",
    "wind_speed_10m",
    "precipitation_3h",
    "temperature_3h_mean",
    "wind_speed_3h_mean",
    "temperature_change_1h",
    "precipitation_change_1h",
    "wind_change_1h",
]

print(
    features[summary_columns]
    .describe()
    .round(3)
)

print("\n=== WEATHER EXTREMES IN THIS SAMPLE ===")

print("\nHighest temperatures:")
print(
    features[
        ["timestamp", "temperature_2m_c"]
    ]
    .sort_values("temperature_2m_c", ascending=False)
    .head(5)
    .to_string(index=False)
)

print("\nHighest precipitation:")
print(
    features[
        ["timestamp", "precipitation_mm"]
    ]
    .sort_values("precipitation_mm", ascending=False)
    .head(5)
    .to_string(index=False)
)

print("\nHighest wind speeds:")
print(
    features[
        ["timestamp", "wind_speed_10m"]
    ]
    .sort_values("wind_speed_10m", ascending=False)
    .head(5)
    .to_string(index=False)
)