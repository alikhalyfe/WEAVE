from pathlib import Path

from ai.data_loader import load_weather_data
from ai.feature_engineering import engineer_features
from ai.regime_analysis import (
    analyze_weather_distributions,
    print_distribution_report,
)


DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "era5_pune_test_clean.csv"
)


df = load_weather_data(DATA_PATH)
features = engineer_features(df)

distributions = analyze_weather_distributions(features)

print_distribution_report(distributions)