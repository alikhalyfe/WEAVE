"""Trains Model A (persistence), Model B (Random Forest) and the AI Model
(gradient-boosted trees) per (target_variable, lead_time_hours), predicts
on the test period, and writes real forecasts into
data/processed/lead_time_targets.csv (test-period rows only -- train-period
rows keep empty forecast columns, matching the "no fabricated forecasts"
rule: we don't report in-sample fit as a forecast).

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


def run() -> pd.DataFrame:
    print("Building modeling dataset (features + lead-time targets)...")
    modeling_df = build_modeling_dataset()

    prediction_blocks = []
    print()
    print(f"{'variable':<20}{'lead_h':>7}{'model':<14}{'MAE':>10}{'n_train':>10}{'n_test':>10}")

    for var in config.TARGET_VARIABLES:
        for lead_h in config.LEAD_TIMES_HOURS:
            train_df, test_df = get_leakage_safe_train_test(modeling_df, lead_h)
            target_col = f"{var}_target_{lead_h}h"

            models = {
                "model_a": PersistenceModel(target_variable=var),
                "model_b": RandomForestModel(var, lead_h, FEATURE_COLUMNS),
                "ai_model": AIModel(var, lead_h, FEATURE_COLUMNS),
            }

            block = test_df[["timestamp", "location"]].copy()
            block["lead_time_hours"] = lead_h
            block["target_variable"] = var

            for name, model in models.items():
                if hasattr(model, "fit"):
                    model.fit(train_df)
                preds = model.predict(test_df, lead_h)
                block[f"{name}_forecast"] = preds["forecast"].values

                evaluable = test_df[target_col].notna() & block[f"{name}_forecast"].notna()
                score = (
                    mae(test_df.loc[evaluable, target_col], block.loc[evaluable, f"{name}_forecast"])
                    if evaluable.any() else float("nan")
                )
                print(f"{var:<20}{lead_h:>7}{name:<14}{score:>10.4f}{len(train_df):>10}{len(test_df):>10}")

            prediction_blocks.append(block)

    predictions_df = pd.concat(prediction_blocks, ignore_index=True)

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
    populated = final["model_a_forecast"].notna().sum()
    print(f"Rows with real forecasts (test period): {populated:,}")

    return final


if __name__ == "__main__":
    run()
