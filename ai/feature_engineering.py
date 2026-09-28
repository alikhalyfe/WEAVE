import pandas as pd


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {
        "timestamp",
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
    }

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns required for feature engineering: {sorted(missing)}"
        )

    features = df.copy()

    # Make sure calculations happen in chronological order within each city.
    if "location" in features.columns:
        features = features.sort_values(
            ["location", "timestamp"]
        ).reset_index(drop=True)
    else:
        features = features.sort_values("timestamp").reset_index(drop=True)

    # Calendar features
    features["hour"] = features["timestamp"].dt.hour
    features["day_of_week"] = features["timestamp"].dt.dayofweek
    features["month"] = features["timestamp"].dt.month

    if "location" in features.columns:
        grouped = features.groupby("location", sort=False)

        # Rolling features are calculated independently for each city.
        features["precipitation_3h"] = (
            grouped["precipitation_mm"]
            .rolling(window=3, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
        )

        features["temperature_3h_mean"] = (
            grouped["temperature_2m_c"]
            .rolling(window=3, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )

        features["wind_speed_3h_mean"] = (
            grouped["wind_speed_10m"]
            .rolling(window=3, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )

        # Hour-to-hour changes are also calculated independently by city.
        features["temperature_change_1h"] = (
            grouped["temperature_2m_c"].diff()
        )

        features["precipitation_change_1h"] = (
            grouped["precipitation_mm"].diff()
        )

        features["wind_change_1h"] = (
            grouped["wind_speed_10m"].diff()
        )

    else:
        features["precipitation_3h"] = (
            features["precipitation_mm"]
            .rolling(window=3, min_periods=1)
            .sum()
        )

        features["temperature_3h_mean"] = (
            features["temperature_2m_c"]
            .rolling(window=3, min_periods=1)
            .mean()
        )

        features["wind_speed_3h_mean"] = (
            features["wind_speed_10m"]
            .rolling(window=3, min_periods=1)
            .mean()
        )

        features["temperature_change_1h"] = (
            features["temperature_2m_c"].diff()
        )

        features["precipitation_change_1h"] = (
            features["precipitation_mm"].diff()
        )

        features["wind_change_1h"] = (
            features["wind_speed_10m"].diff()
        )

    # First observation for each city has no previous hour.
    change_columns = [
        "temperature_change_1h",
        "precipitation_change_1h",
        "wind_change_1h",
    ]

    features[change_columns] = features[change_columns].fillna(0)

    return features