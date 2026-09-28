import numpy as np
import pandas as pd
import pytest

from src.models.persistence import PersistenceModel
from src.models.tree_models import AIModel, RandomForestModel
from src.models.training import get_leakage_safe_train_test


def _synthetic_df(n=60, location="Pune"):
    timestamps = pd.date_range("2021-01-01", periods=n, freq="h")
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "location": location,
            "temperature_2m_c": 20 + rng.normal(0, 1, n),
            "hour": timestamps.hour,
        }
    )
    df["temperature_2m_c_target_6h"] = df["temperature_2m_c"].shift(-6)
    return df


def test_persistence_model_returns_current_value_as_forecast():
    df = _synthetic_df()
    model = PersistenceModel(target_variable="temperature_2m_c")

    result = model.predict(df, lead_time_hours=6)

    assert list(result.columns) == ["timestamp", "location", "lead_time_hours", "forecast"]
    assert (result["forecast"] == df["temperature_2m_c"]).all()
    assert (result["lead_time_hours"] == 6).all()


def test_random_forest_model_fits_and_predicts():
    df = _synthetic_df(n=100)
    model = RandomForestModel(
        target_variable="temperature_2m_c", lead_time_hours=6,
        feature_columns=["temperature_2m_c", "hour"], n_estimators=10,
    )

    model.fit(df.dropna(subset=["temperature_2m_c_target_6h"]))
    result = model.predict(df, lead_time_hours=6)

    assert result["forecast"].notna().all()
    assert result["forecast"].between(0, 40).all()


def test_random_forest_model_rejects_wrong_lead_time():
    model = RandomForestModel("temperature_2m_c", 6, ["temperature_2m_c", "hour"], n_estimators=5)
    model.fit(_synthetic_df(n=50).dropna(subset=["temperature_2m_c_target_6h"]))

    with pytest.raises(ValueError):
        model.predict(_synthetic_df(n=10), lead_time_hours=12)


def test_ai_model_handles_nan_features_natively():
    df = _synthetic_df(n=80)
    df.loc[0:5, "hour"] = np.nan  # simulate lag-feature NaNs at series start

    model = AIModel(
        target_variable="temperature_2m_c", lead_time_hours=6,
        feature_columns=["temperature_2m_c", "hour"], max_iter=20,
    )
    model.fit(df.dropna(subset=["temperature_2m_c_target_6h"]))
    result = model.predict(df, lead_time_hours=6)

    assert result["forecast"].notna().all()  # predicts even where hour is NaN


def test_get_leakage_safe_train_test_excludes_boundary_crossing_rows():
    timestamps = pd.date_range("2024-12-31 12:00:00", periods=20, freq="h")
    df = pd.DataFrame({"timestamp": timestamps, "value": range(20)})
    train_end = pd.Timestamp("2024-12-31 23:00:00")
    test_start = pd.Timestamp("2025-01-01 00:00:00")

    train_df, test_df = get_leakage_safe_train_test(df, lead_time_hours=6, train_end=train_end, test_start=test_start)

    target_time = train_df["timestamp"] + pd.Timedelta(hours=6)
    assert (target_time <= train_end).all()
    assert (test_df["timestamp"] >= test_start).all()
