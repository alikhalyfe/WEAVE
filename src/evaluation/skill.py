"""Forecast skill tables: MAE / RMSE / bias per forecast source, grouped by
any condition columns, plus skill score of each source relative to the
best individual model."""

import numpy as np
import pandas as pd

from src.evaluation.metrics import mae, rmse


def skill_table(df: pd.DataFrame, sources: dict[str, str], by: list[str], actual_col: str = "actual_value") -> pd.DataFrame:
    """Long table: *by, source, n, mae, rmse, bias.

    sources maps display name -> forecast column. Only rows where every
    source and the actual are present are scored, so all sources are
    compared on identical cases.
    """
    cols = list(sources.values())
    scored = df.dropna(subset=[*cols, actual_col])
    rows = []
    for key, g in scored.groupby(by, sort=True) if by else [((), scored)]:
        key = key if isinstance(key, tuple) else (key,)
        for name, col in sources.items():
            rows.append({
                **dict(zip(by, key)),
                "source": name,
                "n": len(g),
                "mae": float(mae(g[actual_col], g[col])),
                "rmse": float(rmse(g[actual_col], g[col])),
                "bias": float((g[col] - g[actual_col]).mean()),
            })
    return pd.DataFrame(rows)


def add_skill_scores(table: pd.DataFrame, by: list[str], members: list[str]) -> pd.DataFrame:
    """Adds best_member_mae and mae_skill_pct = 100 * (1 - mae / best_member_mae):
    positive means the source beats every individual member in that group."""
    table = table.copy()
    best = (
        table[table["source"].isin(members)]
        .groupby(by, sort=False)["mae"].min()
        .rename("best_member_mae")
        .reset_index()
    ) if by else pd.DataFrame({"best_member_mae": [table.loc[table["source"].isin(members), "mae"].min()]})
    table = table.merge(best, on=by, how="left") if by else table.assign(best_member_mae=best["best_member_mae"].iloc[0])
    table["mae_skill_pct"] = 100 * (1 - table["mae"] / table["best_member_mae"].replace(0, np.nan))
    return table
