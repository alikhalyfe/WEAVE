import numpy as np
import pandas as pd


REQUIRED_COLUMNS = [
    "timestamp",
    "location",
    "latitude",
    "longitude",
    "temperature_2m",
    "precipitation",
    "wind_u_10m",
    "wind_v_10m",
]


def validate_schema(df: pd.DataFrame) -> None:
    """Validate that the ERA5 dataset contains the required columns."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing:
        raise ValueError(
            f"Missing required ERA5 columns: {missing}"
        )


def add_wind_speed(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate wind speed from the U and V wind components."""
    df = df.copy()

    df["wind_speed_10m"] = np.sqrt(
        df["wind_u_10m"] ** 2 +
        df["wind_v_10m"] ** 2
    )

    return df


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract useful temporal features."""
    df = df.copy()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df["hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.month

    df["season"] = df["month"].map({
        12: "winter",
        1: "winter",
        2: "winter",

        3: "summer",
        4: "summer",
        5: "summer",

        6: "monsoon",
        7: "monsoon",
        8: "monsoon",
        9: "monsoon",

        10: "post_monsoon",
        11: "post_monsoon",
    })

    return df


def add_rainfall_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create rainfall-related features."""
    df = df.copy()

    # ERA5 precipitation is commonly represented as an accumulated
    # quantity over the dataset's time interval.
    df["precipitation"] = df["precipitation"].clip(lower=0)

    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Run the complete feature-engineering pipeline."""
    validate_schema(df)

    df = df.copy()

    df = add_wind_speed(df)
    df = add_time_features(df)
    df = add_rainfall_features(df)

    return df