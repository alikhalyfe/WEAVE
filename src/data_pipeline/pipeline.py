"""CLI entry point: load -> validate -> feature-engineer -> lead-time
targets -> train/test split -> summary (Tasks 11 & 12).

Run from the repo root: python -m src.data_pipeline.pipeline
"""

import pandas as pd

from src.data_pipeline import config, features, master, split, targets


def run_pipeline() -> dict:
    master_df = master.build_master_dataset()
    master.write_master_dataset(master_df)

    features_df = features.engineer_all_features(master_df)

    lead_time_df = targets.build_lead_time_forecast_dataset(master_df)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    lead_time_df.to_csv(config.LEAD_TIME_TARGETS_PATH, index=False)

    train_df, test_df = split.split_by_time(features_df)
    train_df.to_csv(config.TRAIN_CSV_PATH, index=False)
    test_df.to_csv(config.TEST_CSV_PATH, index=False)

    return {
        "master": master_df,
        "features": features_df,
        "lead_time_targets": lead_time_df,
        "train": train_df,
        "test": test_df,
    }


def print_summary(
    master_df: pd.DataFrame,
    lead_time_df: pd.DataFrame,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> None:
    print()
    print("=== DATA PIPELINE SUMMARY ===")
    print(f"Total rows          : {len(master_df):,}")
    locations = sorted(master_df['location'].unique())
    print(f"Locations ({len(locations)})     : {locations}")
    print(f"Date range          : {master_df['timestamp'].min()} -> {master_df['timestamp'].max()}")
    print("Rows per location   :")
    print(master_df["location"].value_counts().sort_index().to_string())
    print(f"Missing values      : {int(master_df.isna().sum().sum())}")
    print(f"Duplicate rows      : {int(master_df.duplicated().sum())}")
    print(f"Available variables : {list(master_df.columns)}")
    print(f"Lead times (hours)  : {config.LEAD_TIMES_HOURS}")
    print(f"Lead-time dataset   : {len(lead_time_df):,} rows")
    print(f"Train rows          : {len(train_df):,}")
    print(f"Test rows           : {len(test_df):,}")
    print()


def main() -> None:
    print("Loading and validating ERA5 data, generating features and targets...")
    result = run_pipeline()
    print_summary(
        result["master"],
        result["lead_time_targets"],
        result["train"],
        result["test"],
    )


if __name__ == "__main__":
    main()
