from pathlib import Path

from ai.data_loader import load_weather_data


def test_load_weather_data():
    csv_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "era5_pune_test_clean.csv"
    )

    df = load_weather_data(csv_path)

    assert not df.empty

    assert "timestamp" in df.columns
    assert "temperature_2m_c" in df.columns
    assert "precipitation_mm" in df.columns
    assert "wind_speed_10m" in df.columns

    assert df["timestamp"].notna().all()
    assert df["precipitation_mm"].ge(0).all()