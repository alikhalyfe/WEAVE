from dataclasses import dataclass

import pandas as pd

from ai.regime_calibration import CalibrationTable


REGIMES = (
    "Normal",
    "Heavy Rain",
    "Heat",
    "High Wind",
)


@dataclass(frozen=True)
class RegimeThresholds:
    heavy_rain_mm: float
    heat_temperature_c: float
    high_wind_speed_ms: float


def get_thresholds(
    location: str,
    season: str,
    calibration: CalibrationTable,
) -> RegimeThresholds:
    table = calibration.table

    matches = table[
        (table["location"] == location)
        & (table["season"] == season)
    ]

    if matches.empty:
        raise ValueError(
            f"No calibration found for "
            f"{location} / {season}"
        )

    row = matches.iloc[0]

    return RegimeThresholds(
        heavy_rain_mm=float(
            row["precipitation_mm_p95"]
        ),
        heat_temperature_c=float(
            row["temperature_2m_c_p95"]
        ),
        high_wind_speed_ms=float(
            row["wind_speed_10m_p95"]
        ),
    )


def classify_weather_regime(
    row: pd.Series,
    thresholds: RegimeThresholds,
) -> str:

    rain = (
        row["precipitation_mm"] > 0
        and row["precipitation_mm"]
        >= thresholds.heavy_rain_mm
    )

    heat = (
        row["temperature_2m_c"]
        >= thresholds.heat_temperature_c
    )

    wind = (
        row["wind_speed_10m"]
        >= thresholds.high_wind_speed_ms
    )

    # Primary-regime rule.
    #
    # Heavy rain is given priority because it represents
    # the most event-specific precipitation condition.
    if rain:
        return "Heavy Rain"

    if heat:
        return "Heat"

    if wind:
        return "High Wind"

    return "Normal"


def classify_regimes(
    df: pd.DataFrame,
    calibration: CalibrationTable,
) -> pd.DataFrame:

    required_columns = {
        "location",
        "season",
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            "Missing columns required for regime classification: "
            f"{sorted(missing)}"
        )

    result = df.copy()

    result["weather_regime"] = result.apply(
        lambda row: classify_weather_regime(
            row,
            get_thresholds(
                row["location"],
                row["season"],
                calibration,
            ),
        ),
        axis=1,
    )

    return result