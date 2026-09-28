from pathlib import Path

from ai.data_loader import load_multiple_city_data


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


def main():
    df = load_multiple_city_data(
        DATA_DIR,
        CITY_FILES,
    )

    print("\n=== COMBINED DATASET ===")
    print(f"Total rows: {len(df):,}")
    print(f"Total columns: {len(df.columns)}")

    print("\n=== ROWS BY CITY ===")
    print(
        df["location"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\n=== TIME RANGE BY CITY ===")

    time_ranges = (
        df.groupby("location")["timestamp"]
        .agg(["min", "max"])
        .sort_index()
    )

    print(time_ranges.to_string())

    print("\n=== SEASONS BY CITY ===")

    season_counts = (
        df.groupby(["location", "season"])
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )

    print(season_counts.to_string())

    print("\n=== WEATHER SUMMARY BY CITY ===")

    weather_columns = [
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
    ]

    summary = (
        df.groupby("location")[weather_columns]
        .agg(["mean", "min", "max"])
        .round(3)
    )

    print(summary.to_string())

    print("\n=== DUPLICATE TIMESTAMP CHECK ===")

    duplicates = df.duplicated(
        subset=["location", "timestamp"]
    ).sum()

    print(f"Duplicate location/timestamp rows: {duplicates}")

    print("\n=== MISSING VALUES ===")

    missing = df.isna().sum()
    missing = missing[missing > 0]

    if missing.empty:
        print("None")
    else:
        print(missing.to_string())


if __name__ == "__main__":
    main()