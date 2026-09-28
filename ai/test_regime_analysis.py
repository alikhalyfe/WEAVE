from pathlib import Path

from ai.data_loader import load_weather_data
from ai.feature_engineering import engineer_features
from ai.regime_analysis import analyze_weather_distributions


DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "era5_pune_test_clean.csv"
)


def test_weather_distribution_analysis():
    df = load_weather_data(DATA_PATH)
    features = engineer_features(df)

    distributions = analyze_weather_distributions(features)

    assert len(distributions) == 3

    variables = {
        distribution.variable
        for distribution in distributions
    }

    assert variables == {
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
    }

    for distribution in distributions:
        assert distribution.minimum <= distribution.mean
        assert distribution.mean <= distribution.maximum
        assert distribution.p90 <= distribution.p95
        assert distribution.p95 <= distribution.p99