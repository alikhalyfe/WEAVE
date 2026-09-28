from pathlib import Path

from ai.data_loader import load_multiple_city_data
from ai.feature_engineering import engineer_features
from ai.regime_calibration import (
    build_calibration_table,
    calculate_percentile_scores,
)


DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
)

CITY_FILES = [
    "chhatrapati_sambhajinagar_era5_2021_2025_clean.csv",
    "mumbai_era5_2021_2025_clean.csv",
    "nagpur_era5_2021_2025_clean.csv",
    "nashik_era5_2021_2025_clean.csv",
    "pune_era5_2021_2025_clean_correct.csv",
]


PERCENTILE_COLUMNS = [
    "temperature_2m_c_percentile",
    "precipitation_mm_percentile",
    "wind_speed_10m_percentile",
]


def main():
    print("Loading datasets...")

    df = load_multiple_city_data(
        DATA_DIR,
        CITY_FILES,
    )

    print("Engineering features...")

    df = engineer_features(df)

    print("Building historical calibration...")

    calibration = build_calibration_table(df)

    print(
        f"Calibration groups: "
        f"{len(calibration.table)}"
    )

    print("Calculating percentile scores...")

    scored = calculate_percentile_scores(
        df,
        calibration,
    )

    print("\n=== PERCENTILE SCORE SUMMARY ===")

    print(
        scored[PERCENTILE_COLUMNS]
        .describe(
            percentiles=[
                0.50,
                0.75,
                0.90,
                0.95,
                0.99,
            ]
        )
        .round(3)
        .to_string()
    )

    print("\n=== HIGH-PERCENTILE COVERAGE ===")

    for column in PERCENTILE_COLUMNS:
        print(f"\n{column}")

        for threshold in [0.90, 0.95, 0.99]:
            count = (
                scored[column] >= threshold
            ).sum()

            percentage = (
                count / len(scored)
            ) * 100

            print(
                f"  >= {threshold:.2f}: "
                f"{count:,} observations "
                f"({percentage:.2f}%)"
            )

    print("\n=== HIGH-PERCENTILE COVERAGE BY CITY ===")

    for city in sorted(
        scored["location"].unique()
    ):
        city_df = scored[
            scored["location"] == city
        ]

        print(f"\n{city}")

        for column in PERCENTILE_COLUMNS:
            percentage = (
                city_df[column] >= 0.95
            ).mean() * 100

            print(
                f"  {column}: "
                f"{percentage:.2f}% >= P95"
            )

    print("\n=== HIGH-PERCENTILE COVERAGE BY SEASON ===")

    for season in sorted(
        scored["season"].unique()
    ):
        season_df = scored[
            scored["season"] == season
        ]

        print(f"\n{season}")

        for column in PERCENTILE_COLUMNS:
            percentage = (
                season_df[column] >= 0.95
            ).mean() * 100

            print(
                f"  {column}: "
                f"{percentage:.2f}% >= P95"
            )


if __name__ == "__main__":
    main()