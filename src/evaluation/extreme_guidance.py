"""Extreme weather guidance from blended forecasts.

Events are locally calibrated: an observed event is the actual value at or
above the location x season 95th percentile from the training period
(src.regime.classifier.training_thresholds -- the same thresholds that
define the Heavy Rain / Heat / High Wind regimes).

Regression forecasts are smooth, so "forecast >= threshold" misses most
extremes. Guidance therefore issues an event when the blended forecast
exceeds scale * threshold, where scale is tuned per (variable, lead) on the
2024 hindcast to maximise CSI, then frozen and verified on 2025.

event_probability is the skill-weighted share of (bias-corrected) members
that exceed the guidance threshold -- a cheap multi-model agreement signal.
"""

import numpy as np
import pandas as pd

from src.blending.operational import FORECAST_COLUMNS, MODELS
from src.evaluation.extreme_events import event_metrics
from src.regime.classifier import THRESHOLD_COLUMNS

EVENT_NAMES = {
    "precipitation_mm": "Heavy rainfall",
    "temperature_2m_c": "Heat",
    "wind_speed_10m": "High wind",
}
SCALE_GRID = np.round(np.arange(0.30, 1.21, 0.05), 2)


def attach_thresholds(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    """Adds event_threshold (per row's variable/location/season) and
    observed_event (NaN where the actual isn't known yet)."""
    long = thresholds.melt(id_vars=["location", "season"], var_name="threshold_col", value_name="event_threshold")
    long["target_variable"] = long["threshold_col"].map({v: k for k, v in THRESHOLD_COLUMNS.items()})
    out = df.merge(long.drop(columns="threshold_col"), on=["location", "season", "target_variable"], how="left")
    out["observed_event"] = (out["actual_value"] >= out["event_threshold"]).where(out["actual_value"].notna())
    return out


def tune_scales(df: pd.DataFrame, forecast_col: str = "blended") -> dict[tuple[str, int], float]:
    """CSI-maximising threshold scale per (target_variable, lead_time_hours)."""
    scales = {}
    scored = df.dropna(subset=[forecast_col, "observed_event", "event_threshold"])
    for key, g in scored.groupby(["target_variable", "lead_time_hours"]):
        observed = g["observed_event"].astype(bool).to_numpy()
        csis = [event_metrics(observed, g[forecast_col].to_numpy() >= s * g["event_threshold"].to_numpy())["csi"] for s in SCALE_GRID]
        scales[(key[0], int(key[1]))] = float(SCALE_GRID[int(np.argmax(csis))])
    return scales


def apply_guidance(df: pd.DataFrame, scales: dict[tuple[str, int], float], weight_prefix: str = "weight_") -> pd.DataFrame:
    """Adds guidance_threshold, guidance_event and event_probability."""
    out = df.copy()
    scale = [scales.get((v, int(l)), 1.0) for v, l in zip(out["target_variable"], out["lead_time_hours"])]
    out["guidance_threshold"] = out["event_threshold"] * np.array(scale)
    out["guidance_event"] = out["blended"] >= out["guidance_threshold"]

    members = out[FORECAST_COLUMNS].to_numpy(float) - out[[f"bias_{m}" for m in MODELS]].to_numpy(float)
    weights = out[[f"{weight_prefix}{m}" for m in MODELS]].to_numpy(float)
    exceed = members >= out["guidance_threshold"].to_numpy()[:, None]
    out["event_probability"] = (weights * exceed).sum(axis=1) / weights.sum(axis=1)
    return out


def verify_events(df: pd.DataFrame, sources: dict[str, pd.Series]) -> pd.DataFrame:
    """POD / FAR / CSI / frequency bias per (variable, lead) for each source.
    sources maps name -> boolean Series of forecast events aligned to df."""
    rows = []
    mask = df["observed_event"].notna()
    for key, idx in df[mask].groupby(["target_variable", "lead_time_hours"]).groups.items():
        observed = df.loc[idx, "observed_event"].astype(bool).to_numpy()
        for name, events in sources.items():
            predicted = events.loc[idx].astype(bool).to_numpy()
            m = event_metrics(observed, predicted)
            rows.append({
                "target_variable": key[0],
                "event": EVENT_NAMES.get(key[0], key[0]),
                "lead_time_hours": int(key[1]),
                "source": name,
                "observed_events": int(observed.sum()),
                "forecast_events": int(predicted.sum()),
                "pod": float(m["recall"]),
                "far": float(1 - m["precision"]) if predicted.any() else 0.0,
                "csi": float(m["csi"]),
                "frequency_bias": float(predicted.sum() / observed.sum()) if observed.any() else float("nan"),
            })
    return pd.DataFrame(rows)
