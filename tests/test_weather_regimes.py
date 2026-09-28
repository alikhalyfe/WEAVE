import pandas as pd


def test_weather_regimes():
    data = pd.read_csv("data/weather_regimes.csv")

    assert len(data) == 219120
    assert data["location"].nunique() == 5

    expected_regimes = {"Normal", "Heat", "High Wind", "Heavy Rain"}
    assert set(data["weather_regime"].unique()) == expected_regimes

    assert data["timestamp"].notna().all()
    assert data["weather_regime"].notna().all()


if __name__ == "__main__":
    test_weather_regimes()
    print("Weather regime test PASSED")