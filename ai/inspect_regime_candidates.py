from pathlib import Path

import pandas as pd

from ai.data_loader import load_multiple_city_data
from ai.feature_engineering import engineer_features
from ai.regime_calibration import build_calibration_table


DATA_DIR = Path("data")

DATASETS = [
    "chhatrapati_sambhajinagar_era5_2021_2025_clean.csv",
    "mumbai_era5_2021_2025_clean.csv",
    "nagpur_era5_2021_2025_clean.csv",
    "nashik_era5_2021_2025_clean.csv",
    "pune_era5_2021_2025_clean_correct.csv",
]


def print_threshold_table(calibration: pd.DataFrame) -> None:
    print("\n=== CITY × SEASON CANDIDATE THRESHOLDS ===")

    for _, row in calibration.iterrows():
        print(
            f"\n{row['location']} | {row['season']}"
        )

        print(
            f"  Temperature: "
            f"P90={row['temperature_2m_c_p90']:.2f}°C | "
            f"P95={row['temperature_2m_c_p95']:.2f}°C | "
            f"P99={row['temperature_2m_c_p99']:.2f}°C"
        )

        print(
            f"  Rain/hour:   "
            f"P90={row['precipitation_mm_p90']:.3f} mm | "
            f"P95={row['precipitation_mm_p95']:.3f} mm | "
            f"P99={row['precipitation_mm_p99']:.3f} mm"
        )

        print(
            f"  Wind:        "
            f"P90={row['wind_speed_10m_p90']:.2f} m/s | "
            f"P95={row['wind_speed_10m_p95']:.2f} m/s | "
            f"P99={row['wind_speed_10m_p99']:.2f} m/s"
        )


def print_candidate_coverage(
    df: pd.DataFrame,
    calibration: pd.DataFrame,
) -> None:
    result = df.copy()

    calibration_lookup = calibration.set_index(
        ["location", "season"]
    )

    keys = pd.MultiIndex.from_frame(
        result[["location", "season"]]
    )

    for variable in [
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
    ]:
        for percentile in [90, 95, 99]:
            threshold_column = f"{variable}_p{percentile}"

            thresholds = calibration_lookup.loc[
                keys,
                threshold_column,
            ].to_numpy()

            result[f"{variable}_ge_p{percentile}"] = (
                result[variable].to_numpy() >= thresholds
            )

    # Positive-rain-only candidates.
    result["rain_positive"] = result["precipitation_mm"] > 0

    print("\n=== CANDIDATE COVERAGE ===")

    total = len(result)

    candidates = {
        "Heat P90": result["temperature_2m_c_ge_p90"],
        "Heat P95": result["temperature_2m_c_ge_p95"],
        "Heat P99": result["temperature_2m_c_ge_p99"],
        "Heavy Rain P90": (
            result["rain_positive"]
            & result["precipitation_mm_ge_p90"]
        ),
        "Heavy Rain P95": (
            result["rain_positive"]
            & result["precipitation_mm_ge_p95"]
        ),
        "Heavy Rain P99": (
            result["rain_positive"]
            & result["precipitation_mm_ge_p99"]
        ),
        "High Wind P90": result["wind_speed_10m_ge_p90"],
        "High Wind P95": result["wind_speed_10m_ge_p95"],
        "High Wind P99": result["wind_speed_10m_ge_p99"],
    }

    for name, mask in candidates.items():
        count = int(mask.sum())
        percentage = count / total * 100

        print(
            f"{name:<20} "
            f"{count:>7,} observations "
            f"({percentage:>6.2f}%)"
        )


def print_overlap_analysis(
    df: pd.DataFrame,
    calibration: pd.DataFrame,
) -> None:
    print("\n=== REGIME CANDIDATE OVERLAP ===")

    calibration_lookup = calibration.set_index(
        ["location", "season"]
    )

    keys = pd.MultiIndex.from_frame(
        df[["location", "season"]]
    )

    temperature_thresholds = calibration_lookup.loc[
        keys,
        "temperature_2m_c_p95",
    ].to_numpy()

    precipitation_thresholds = calibration_lookup.loc[
        keys,
        "precipitation_mm_p95",
    ].to_numpy()

    wind_thresholds = calibration_lookup.loc[
        keys,
        "wind_speed_10m_p95",
    ].to_numpy()

    heat = (
        df["temperature_2m_c"].to_numpy()
        >= temperature_thresholds
    )

    rain = (
        (df["precipitation_mm"].to_numpy() > 0)
        & (
            df["precipitation_mm"].to_numpy()
            >= precipitation_thresholds
        )
    )

    wind = (
        df["wind_speed_10m"].to_numpy()
        >= wind_thresholds
    )

    combinations = {
        "Heat only": heat & ~rain & ~wind,
        "Heavy Rain only": rain & ~heat & ~wind,
        "High Wind only": wind & ~heat & ~rain,
        "Heat + Heavy Rain": heat & rain & ~wind,
        "Heat + High Wind": heat & wind & ~rain,
        "Heavy Rain + High Wind": rain & wind & ~heat,
        "All three": heat & rain & wind,
        "None": ~heat & ~rain & ~wind,
    }

    total = len(df)

    for name, mask in combinations.items():
        count = int(mask.sum())
        percentage = count / total * 100

        print(
            f"{name:<25} "
            f"{count:>7,} observations "
            f"({percentage:>6.2f}%)"
        )

def print_rain_analysis(df: pd.DataFrame) -> None:
    print("\n=== RAINFALL ANALYSIS ===")

    positive_rain = df.loc[
        df["precipitation_mm"] > 0,
        "precipitation_mm",
    ]

    print(
        f"Positive-rain observations: "
        f"{len(positive_rain):,} "
        f"({len(positive_rain) / len(df) * 100:.2f}%)"
    )

    print("\nPositive rainfall distribution:")

    for percentile in [50, 75, 90, 95, 99]:
        value = positive_rain.quantile(percentile / 100)
        print(
            f"  P{percentile}: {value:.3f} mm/hour"
        )

    print(
        f"  Maximum: {positive_rain.max():.3f} mm/hour"
    )

def print_overlap_examples(
    df: pd.DataFrame,
    calibration: pd.DataFrame,
) -> None:
    print("\n=== OVERLAP EXAMPLES ===")

    calibration_lookup = calibration.set_index(
        ["location", "season"]
    )

    keys = pd.MultiIndex.from_frame(
        df[["location", "season"]]
    )

    temp_p95 = calibration_lookup.loc[
        keys, "temperature_2m_c_p95"
    ].to_numpy()

    rain_p95 = calibration_lookup.loc[
        keys, "precipitation_mm_p95"
    ].to_numpy()

    wind_p95 = calibration_lookup.loc[
        keys, "wind_speed_10m_p95"
    ].to_numpy()

    heat = df["temperature_2m_c"].to_numpy() >= temp_p95

    rain = (
        (df["precipitation_mm"].to_numpy() > 0)
        & (df["precipitation_mm"].to_numpy() >= rain_p95)
    )

    wind = df["wind_speed_10m"].to_numpy() >= wind_p95

    result = df.copy()
    result["heat_candidate"] = heat
    result["rain_candidate"] = rain
    result["wind_candidate"] = wind

    overlap_groups = {
        "Heavy Rain + High Wind":
            rain & wind & ~heat,

        "Heat + High Wind":
            heat & wind & ~rain,

        "Heat + Heavy Rain":
            heat & rain & ~wind,

        "All three":
            heat & rain & wind,
    }

    columns = [
        "timestamp",
        "location",
        "season",
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
        "precipitation_3h",
        "temperature_3h_mean",
        "wind_speed_3h_mean",
    ]

    for name, mask in overlap_groups.items():
        subset = result.loc[mask, columns]

        print(f"\n{name}: {len(subset):,} observations")

        if subset.empty:
            continue

        print(
            subset.head(10).to_string(
                index=False,
                float_format=lambda value: f"{value:.3f}",
            )
        )

def main() -> None:
    print("Loading datasets...")

    df = load_multiple_city_data(
        DATA_DIR,
        DATASETS,
    )

    print(f"Loaded {len(df):,} observations.")

    print("\nEngineering features...")
    df = engineer_features(df)

    print("\nBuilding city × season calibration...")
    calibration_result = build_calibration_table(df)

    calibration = calibration_result.table

    print_threshold_table(calibration)

    print_candidate_coverage(
        df,
        calibration,
    )

    print_overlap_analysis(df, calibration)
    print_overlap_examples(df, calibration)
    print_rain_analysis(df)

    print("\n=== ANALYSIS COMPLETE ===")


if __name__ == "__main__":
    main()