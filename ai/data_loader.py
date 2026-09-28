from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "timestamp",
    "location",
    "latitude",
    "longitude",
    "temperature_2m_c",
    "precipitation_mm",
    "u10",
    "v10",
    "wind_speed_10m",
    "season",
}


def load_weather_data(csv_path: str | Path) -> pd.DataFrame:
    """
    Load and validate the WEAVE ERA5 weather dataset.

    Returns:
        A cleaned pandas DataFrame with a parsed timestamp.

    Raises:
        FileNotFoundError: If the CSV does not exist.
        ValueError: If the dataset fails validation.
    """

    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # 1. Validate schema
    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    # 2. Parse timestamps
    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    if df["timestamp"].isna().any():
        raise ValueError("Dataset contains invalid timestamps.")

    # 3. Check missing values
    missing_values = df[list(REQUIRED_COLUMNS)].isna().sum()

    if missing_values.any():
        bad_columns = missing_values[missing_values > 0].to_dict()

        raise ValueError(
            f"Dataset contains missing values: {bad_columns}"
        )

    # 4. Check duplicate rows
    if df.duplicated().any():
        raise ValueError("Dataset contains duplicate rows.")

    # 5. Check duplicate timestamps per location
    duplicate_timestamps = df.duplicated(
        subset=["timestamp", "location"]
    )

    if duplicate_timestamps.any():
        raise ValueError(
            "Dataset contains duplicate timestamp/location combinations."
        )

    # 6. Validate numeric columns
    numeric_columns = [
        "latitude",
        "longitude",
        "temperature_2m_c",
        "precipitation_mm",
        "u10",
        "v10",
        "wind_speed_10m",
    ]

    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise ValueError(
                f"Column '{column}' must contain numeric values."
            )

    # 7. Validate precipitation
    if (df["precipitation_mm"] < 0).any():
        raise ValueError("Precipitation cannot be negative.")

    # 8. Validate wind speed against U/V components
    calculated_wind = (
        df["u10"] ** 2 + df["v10"] ** 2
    ) ** 0.5

    wind_difference = (
        calculated_wind - df["wind_speed_10m"]
    ).abs()

    if wind_difference.max() > 0.01:
        raise ValueError(
            "wind_speed_10m does not match the provided u10/v10 values."
        )

    # 9. Sort chronologically
    df = df.sort_values(
        ["location", "timestamp"]
    ).reset_index(drop=True)

    return df

def load_multiple_city_data(
    data_directory: str | Path,
    filenames: list[str],
) -> pd.DataFrame:
    """
    Load and combine multiple city ERA5 datasets.

    Each file is independently validated using
    load_weather_data() before being combined.
    """

    data_directory = Path(data_directory)

    if not data_directory.exists():
        raise FileNotFoundError(
            f"Data directory not found: {data_directory}"
        )

    if not filenames:
        raise ValueError("No dataset filenames were provided.")

    datasets = []

    for filename in filenames:
        file_path = data_directory / filename

        print(f"Loading: {filename}")

        city_df = load_weather_data(file_path)

        datasets.append(city_df)

    combined = pd.concat(
        datasets,
        ignore_index=True,
    )

    # Sort the complete dataset chronologically by location.
    combined = combined.sort_values(
        ["location", "timestamp"]
    ).reset_index(drop=True)

    return combined