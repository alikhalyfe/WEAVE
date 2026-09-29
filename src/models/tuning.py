"""Leak-free hyperparameter selection for the AI model (gradient-boosted trees).

For every (target variable, lead time), each candidate below is fitted on
2021-2022 (targets landing in 2022 at the latest) and scored by MAE on
2023. The winner is written to tuned_params.json and used by
generate_forecasts for both the 2024 hindcast and the 2025 run. 2024 and
2025 are never seen during tuning.

    python -m src.models.tuning
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from src.data_pipeline import config
from src.evaluation.metrics import mae
from src.models.training import FEATURE_COLUMNS, build_modeling_dataset, get_leakage_safe_train_test
from src.models.tree_models import AIModel

TUNED_PATH = Path(__file__).with_name("tuned_params.json")
FIT_END = pd.Timestamp("2022-12-31 23:00:00")
VALID_START, VALID_END = pd.Timestamp("2023-01-01 00:00:00"), pd.Timestamp("2023-12-31 23:00:00")
MIN_SPREAD_RATIO = 0.2

CANDIDATES = {
    "baseline": {"max_iter": 150},
    "deeper": {"max_iter": 500, "learning_rate": 0.05, "max_leaf_nodes": 63, "l2_regularization": 1.0},
    "median": {"max_iter": 500, "learning_rate": 0.05, "loss": "absolute_error"},
    "wide": {"max_iter": 300, "learning_rate": 0.08, "max_leaf_nodes": 127, "min_samples_leaf": 40},
}


def load_tuned() -> dict[str, dict]:
    """{'<variable>|<lead>': params}; empty when tuning hasn't run."""
    return json.loads(TUNED_PATH.read_text()) if TUNED_PATH.exists() else {}


def run() -> dict:
    t0 = time.time()
    modeling_df = build_modeling_dataset()
    chosen, report = {}, []
    for var in config.TARGET_VARIABLES:
        for lead in config.LEAD_TIMES_HOURS:
            train_df, valid_df = get_leakage_safe_train_test(modeling_df, lead, FIT_END, VALID_START)
            valid_df = valid_df[valid_df["timestamp"] <= VALID_END]
            target = f"{var}_target_{lead}h"
            valid_df = valid_df[valid_df[target].notna()]
            scores, degenerate = {}, set()
            for name, params in CANDIDATES.items():
                model = AIModel(var, lead, FEATURE_COLUMNS, **{"random_state": 0, **params}).fit(train_df)
                pred = model.predict(valid_df, lead)["forecast"]
                scores[name] = float(mae(valid_df[target], pred))
                # MAE rewards predicting the median; for zero-inflated rain that is
                # "always 0 mm", which can never forecast rain. Reject any model
                # whose predictions barely vary relative to the truth.
                if pred.std() < MIN_SPREAD_RATIO * valid_df[target].std():
                    degenerate.add(name)
            best = min((n for n in scores if n not in degenerate), key=scores.get)
            chosen[f"{var}|{lead}"] = CANDIDATES[best]
            report.append({"variable": var, "lead": lead, "best": best, "rejected": sorted(degenerate), **{k: round(v, 4) for k, v in scores.items()}})
            print(f"{var:18s} {lead:>3}h  best={best:9s}  " + "  ".join(f"{k}={v:.4f}{'(degenerate)' if k in degenerate else ''}" for k, v in scores.items()), flush=True)
    TUNED_PATH.write_text(json.dumps(chosen, indent=1))
    print(f"Wrote {TUNED_PATH} in {time.time() - t0:.0f}s")
    return {"chosen": chosen, "report": report}


if __name__ == "__main__":
    run()
