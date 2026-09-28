from pathlib import Path

from ai.data_loader import load_multiple_city_data
from ai.feature_engineering import engineer_features


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


WEATHER_COLUMNS = [
    "temperature_2m_c",
    "precipitation_mm",
    "wind_speed_10m",
]


def main():
    print("Loading all city datasets...")

    df = load_multiple_city_data(
        DATA_DIR,
        CITY_FILES,
    )

    print("Engineering features...")

    df = engineer_features(df)

    print("\n=== CITY × SEASON DISTRIBUTIONS ===")

    for city in sorted(df["location"].unique()):
        print(f"\n{'=' * 70}")
        print(f"CITY: {city}")
        print(f"{'=' * 70}")

        city_df = df[df["location"] == city]

        for season in sorted(city_df["season"].unique()):
            season_df = city_df[
                city_df["season"] == season
            ]

            print(f"\n--- {season} ---")

            for column in WEATHER_COLUMNS:
                values = season_df[column]

                print(
                    f"{column:25s} "
                    f"P90={values.quantile(0.90):7.3f}  "
                    f"P95={values.quantile(0.95):7.3f}  "
                    f"P99={values.quantile(0.99):7.3f}  "
                    f"MAX={values.max():7.3f}"
                )


if __name__ == "__main__":
    main()