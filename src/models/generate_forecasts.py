"""Trains Model A (persistence), Model B (Random Forest) and the AI Model
(gradient-boosted trees) per (target_variable, lead_time_hours) and writes
real out-of-sample forecasts into data/processed/lead_time_targets.csv.

Two runs, each strictly out-of-sample:

    hindcast    train 2021-2023 -> forecast 2024  (skill history for weights)
    operational train 2021-2024 -> forecast 2025  (evaluation period)

2021-2023 rows keep empty forecast columns -- we don't report in-sample fit
as a forecast.

Run from the repo root: python -m src.models.generate_forecasts
"""

import pandas as pd

from src.data_pipeline import config
from src.data_pipeline.master import build_master_dataset
from src.data_pipeline.targets import build_lead_time_forecast_dataset
from src.evaluation.metrics import mae
from src.models.persistence import PersistenceModel
from src.models.tree_models import AIModel, RandomForestModel
from src.models.training import FEATURE_COLUMNS, build_modeling_dataset, get_leakage_safe_train_test
from src.models.tuning import load_tuned

FORECAST_RUNS = [
    ("hindcast", config.HINDCAST_TRAIN_END, config.HINDCAST_START, config.HINDCAST_END),
    ("operational", config.TRAIN_END, config.TEST_START, config.TEST_END),
]


def forecast_window(
    modeling_df: pd.DataFrame,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
    run_name: str = "",
) -> pd.DataFrame:
    """Fit all models on data whose targets land at/before train_end and
    predict issue times in [test_start, test_end] (AI model hyperparameters
    from tuning.py, chosen on 2023 only). Long format, one row per
    (timestamp, location, lead_time_hours, target_variable)."""
    tuned = load_tuned()
    blocks = []
    for var in config.TARGET_VARIABLES:
        for lead_h in config.LEAD_TIMES_HOURS:
            train_df, test_df = get_leakage_safe_train_test(modeling_df, lead_h, train_end, test_start)
            test_df = test_df[test_df["timestamp"] <= test_end]
            target_col = f"{var}_target_{lead_h}h"

            models = {
                "model_a": PersistenceModel(target_variable=var),
                "model_b": RandomForestModel(var, lead_h, FEATURE_COLUMNS),
                "ai_model": AIModel(var, lead_h, FEATURE_COLUMNS, **tuned.get(f"{var}|{lead_h}", {})),
            }

            block = test_df[["timestamp", "location"]].copy()
            block["lead_time_hours"] = lead_h
            block["target_variable"] = var

            for name, model in models.items():
                if hasattr(model, "fit"):
                    model.fit(train_df)
                block[f"{name}_forecast"] = model.predict(test_df, lead_h)["forecast"].values

                evaluable = test_df[target_col].notna() & block[f"{name}_forecast"].notna()
                score = (
                    mae(test_df.loc[evaluable, target_col], block.loc[evaluable, f"{name}_forecast"])
                    if evaluable.any() else float("nan")
                )
                print(f"{run_name:<12}{var:<20}{lead_h:>7}  {name:<10}{score:>10.4f}{len(train_df):>10}{len(test_df):>10}")

            blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


def run() -> pd.DataFrame:
    print("Building modeling dataset (features + lead-time targets)...")
    modeling_df = build_modeling_dataset()

    print()
    print(f"{'run':<12}{'variable':<20}{'lead_h':>7}  {'model':<10}{'MAE':>10}{'n_train':>10}{'n_test':>10}")
    predictions_df = pd.concat(
        [forecast_window(modeling_df, *window, run_name=name) for name, *window in FORECAST_RUNS],
        ignore_index=True,
    )

    print()
    print("Merging predictions into the lead-time forecast dataset...")
    base = build_lead_time_forecast_dataset(build_master_dataset())
    base = base.drop(columns=["model_a_forecast", "model_b_forecast", "ai_model_forecast"])

    final = base.merge(
        predictions_df,
        on=["timestamp", "location", "lead_time_hours", "target_variable"],
        how="left",
    )
    final = final[
        [
            "timestamp", "location", "latitude", "longitude", "lead_time_hours",
            "target_variable", "model_a_forecast", "model_b_forecast",
            "ai_model_forecast", "actual_value", "season",
        ]
    ]

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    final.to_csv(config.LEAD_TIME_TARGETS_PATH, index=False)
    print(f"Wrote {len(final):,} rows to {config.LEAD_TIME_TARGETS_PATH}")
    print(f"Rows with real forecasts (2024 hindcast + 2025): {final['model_a_forecast'].notna().sum():,}")

    return final


if __name__ == "__main__":
    run()
