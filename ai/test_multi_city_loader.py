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


def test_load_multiple_city_data():
    df = load_multiple_city_data(
        DATA_DIR,
        CITY_FILES,
    )

    assert not df.empty

    expected_cities = {
        "Chhatrapati Sambhajinagar",
        "Mumbai",
        "Nagpur",
        "Nashik",
        "Pune",
    }

    assert set(df["location"].unique()) == expected_cities

    assert df["timestamp"].notna().all()

    assert df["temperature_2m_c"].notna().all()
    assert df["precipitation_mm"].notna().all()
    assert df["wind_speed_10m"].notna().all()