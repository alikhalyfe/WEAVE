from dataclasses import dataclass

import pandas as pd


WEATHER_VARIABLES = (
    "temperature_2m_c",
    "precipitation_mm",
    "wind_speed_10m",
)


PERCENTILES = (
    0.50,
    0.75,
    0.90,
    0.95,
    0.99,
)


@dataclass(frozen=True)
class CalibrationTable:
    """
    Historical percentile baselines for one
    location + season combination.
    """

    table: pd.DataFrame


def build_calibration_table(df: pd.DataFrame) -> CalibrationTable:
    required_columns = {
        "location",
        "season",
        *WEATHER_VARIABLES,
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns required for calibration: {sorted(missing)}"
        )

    rows = []

    grouped = df.groupby(
        ["location", "season"],
        sort=True,
    )

    for (location, season), group in grouped:
        row = {
            "location": location,
            "season": season,
        }

        # Temperature and wind use all observations.
        for variable in [
            "temperature_2m_c",
            "wind_speed_10m",
        ]:
            values = group[variable].dropna()

            for percentile in PERCENTILES:
                name = f"{variable}_p{int(percentile * 100)}"
                row[name] = float(
                    values.quantile(percentile)
                )

        # Rainfall is zero-heavy, so calibrate intensity
        # using positive-rain observations only.
        rain_values = group.loc[
            group["precipitation_mm"] > 0,
            "precipitation_mm",
        ].dropna()

        for percentile in PERCENTILES:
            name = (
                f"precipitation_mm_p"
                f"{int(percentile * 100)}"
            )

            if rain_values.empty:
                row[name] = float("nan")
            else:
                row[name] = float(
                    rain_values.quantile(percentile)
                )


            row[name] = float(
                rain_values.quantile(percentile)
            )
        rows.append(row)

    calibration = pd.DataFrame(rows)

    return CalibrationTable(table=calibration)


def calculate_percentile_scores(
    df: pd.DataFrame,
    calibration: CalibrationTable,
) -> pd.DataFrame:
    """
    Calculate empirical percentile ranks for each weather
    variable within each location × season distribution.

    A score of:
        0.50 = approximately median
        0.90 = approximately 90th percentile
        0.95 = approximately 95th percentile
        0.99 = approximately 99th percentile
    """

    required_columns = {
        "location",
        "season",
        *WEATHER_VARIABLES,
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns required for percentile scoring: "
            f"{sorted(missing)}"
        )

    result = df.copy()

    # Verify that every location/season combination has
    # a calibration baseline.
    calibration_groups = set(
        zip(
            calibration.table["location"],
            calibration.table["season"],
        )
    )

    data_groups = set(
        zip(
            result["location"],
            result["season"],
        )
    )

    missing_groups = data_groups - calibration_groups

    if missing_groups:
        raise ValueError(
            "Missing calibration groups: "
            f"{sorted(missing_groups)}"
        )

    # Calculate empirical percentile rank independently
    # for every location × season combination.
    grouped = result.groupby(
        ["location", "season"],
        sort=False,
    )

    for variable in WEATHER_VARIABLES:
        score_column = f"{variable}_percentile"

        result[score_column] = grouped[variable].rank(
            method="average",
            pct=True,
        )

    return result