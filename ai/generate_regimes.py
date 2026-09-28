from pathlib import Path

from ai.data_loader import load_multiple_city_data
from ai.regime_calibration import build_calibration_table
from ai.regime_classifier import classify_regimes


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "weather_regimes.csv"

CITY_FILES = [
    "chhatrapati_sambhajinagar_era5_2021_2025_clean.csv",
    "mumbai_era5_2021_2025_clean.csv",
    "nagpur_era5_2021_2025_clean.csv",
    "nashik_era5_2021_2025_clean.csv",
    "pune_era5_2021_2025_clean_correct.csv",
]


def main():
    print("Loading weather datasets...")

    df = load_multiple_city_data(
        DATA_DIR,
        CITY_FILES,
    )

    print(f"Loaded {len(df):,} observations.")

    print("Building city × season calibration...")
    calibration = build_calibration_table(df)

    print("Classifying weather regimes...")
    classified = classify_regimes(
        df,
        calibration,
    )

    output_columns = [
        "timestamp",
        "location",
        "latitude",
        "longitude",
        "season",
        "weather_regime",
    ]

    output = classified[output_columns].copy()

    output = output.sort_values(
        ["location", "timestamp"]
    ).reset_index(drop=True)

    output.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("=== WEATHER REGIME OUTPUT ===")
    print(f"Rows       : {len(output):,}")
    print(f"Columns    : {list(output.columns)}")
    print(f"Output     : {OUTPUT_PATH}")
    print()

    print("=== REGIME COUNTS ===")
    print(output["weather_regime"].value_counts())

    print()
    print("=== REGIME PERCENTAGES ===")
    percentages = (
        output["weather_regime"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
    )
    print(percentages)

    print()
    print("=== SAMPLE ===")
    print(output.head(10).to_string(index=False))


if __name__ == "__main__":
    main()