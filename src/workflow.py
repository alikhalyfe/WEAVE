"""WEAVE operational workflow: one command from raw ERA5 CSVs to the
artifacts the API and dashboard serve.

    python -m src.workflow            # reuse forecasts if already generated
    python -m src.workflow --retrain  # retrain all models first

Stages
    1. forecasts   Model A/B/AI hindcast (2024) + operational (2025) runs
    2. regimes     weather regime per issue time (train-calibrated)
    3. blending    rolling-origin adaptive blend, 3 configurations x 4 methods
    4. selection   per (variable, lead) candidate chosen on the 2024 hindcast
    5. evaluation  2025 skill vs every member, by variable/lead/location/season
    6. extremes    CSI-tuned guidance thresholds (2024) verified on 2025
    7. export      data/processed/artifacts/{forecasts.csv, *.json}
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.blending.operational import CONFIGS, FORECAST_COLUMNS, METHODS, MODELS, run_rolling_blend
from src.data_pipeline import config
from src.data_pipeline.master import build_master_dataset
from src.evaluation.extreme_guidance import EVENT_NAMES, apply_guidance, attach_thresholds, tune_scales, verify_events
from src.evaluation.skill import add_skill_scores, skill_table
from src.regime.classifier import build_regimes, training_thresholds

ARTIFACTS_DIR = config.PROCESSED_DIR / "artifacts"
MODEL_LABELS = {
    "model_a": "Persistence",
    "model_b": "Random Forest",
    "ai_model": "AI (Gradient Boosting)",
}
MEMBER_SOURCES = {m: f"{m}_forecast" for m in MODELS}


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_archive(retrain: bool = False) -> pd.DataFrame:
    path = config.LEAD_TIME_TARGETS_PATH
    if not retrain and path.exists():
        archive = pd.read_csv(path, parse_dates=["timestamp"])
        if archive.loc[archive["timestamp"] < config.TEST_START, "model_a_forecast"].notna().any():
            return archive
        _log("Existing forecasts have no 2024 hindcast -- regenerating.")
    from src.models.generate_forecasts import run as generate_forecasts
    return generate_forecasts()


def candidate_column(cfg: str, method: str) -> str:
    return f"blend__{cfg}__{method}"


CANDIDATES = [(cfg, method) for cfg in CONFIGS for method in METHODS]
PER_CANDIDATE = [
    *(f"w_{method}_{m}" for method in METHODS for m in MODELS),
    *(f"bias_{m}" for m in MODELS), *(f"mae_{m}" for m in MODELS), "n_history", "fallback_level",
]


def blend_all_configs(archive: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run the rolling blend once per configuration. Returns the shared row
    frame (with one blended column per candidate) and each config's
    per-row weights/bias/level, row-aligned with it."""
    base, params = None, {}
    for cfg, spec in CONFIGS.items():
        out = run_rolling_blend(archive, config.HINDCAST_START, config.TEST_END,
                                levels=spec["levels"], bias_correct=spec["bias_correct"])
        if base is None:
            base = out.drop(columns=[c for c in out.columns if c.startswith("blended_") or c in PER_CANDIDATE])
        elif not (out["timestamp"].equals(base["timestamp"]) and out["location"].equals(base["location"])):
            raise RuntimeError(f"Config {cfg} produced rows in a different order")
        for method in METHODS:
            base[candidate_column(cfg, method)] = out[f"blended_{method}"].to_numpy()
        params[cfg] = out[PER_CANDIDATE]
    return base, params


def select_candidates(hindcast: pd.DataFrame) -> dict[tuple[str, int], tuple[str, str]]:
    """Lowest-MAE (configuration, method) per (variable, lead) on the 2024 hindcast."""
    sources = {f"{cfg}.{method}": candidate_column(cfg, method) for cfg, method in CANDIDATES}
    table = skill_table(hindcast, sources, ["target_variable", "lead_time_hours"])
    best = table.loc[table.groupby(["target_variable", "lead_time_hours"])["mae"].idxmin()]
    return {(r.target_variable, int(r.lead_time_hours)): tuple(r.source.split(".")) for r in best.itertuples()}


def apply_selection(df: pd.DataFrame, params: dict[str, pd.DataFrame], selection: dict) -> pd.DataFrame:
    """Fill blended / weight_* / bias_* / level columns from each row's selected candidate."""
    df = df.copy()
    key = list(zip(df["target_variable"], df["lead_time_hours"].astype(int)))
    df["blend_config"] = [selection[k][0] for k in key]
    df["blend_method"] = [selection[k][1] for k in key]
    df["blended"] = np.nan
    for (cfg, method) in set(selection.values()):
        rows = ((df["blend_config"] == cfg) & (df["blend_method"] == method)).to_numpy()
        p = params[cfg]
        df.loc[rows, "blended"] = df.loc[rows, candidate_column(cfg, method)]
        for m in MODELS:
            df.loc[rows, f"weight_{m}"] = p.loc[rows, f"w_{method}_{m}"].to_numpy()
            df.loc[rows, f"bias_{m}"] = p.loc[rows, f"bias_{m}"].to_numpy()
            df.loc[rows, f"mae_{m}"] = p.loc[rows, f"mae_{m}"].to_numpy()
        df.loc[rows, "n_history"] = p.loc[rows, "n_history"].to_numpy()
        df.loc[rows, "fallback_level"] = p.loc[rows, "fallback_level"].to_numpy()
    df["n_history"] = df["n_history"].astype(int)
    return df


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def build_weight_maps(ev: pd.DataFrame) -> dict:
    wcols = [f"weight_{m}" for m in MODELS]

    def summarise(by, frame=ev):
        t = frame.groupby(by)[wcols].mean().reset_index()
        t["dominant_model"] = t[wcols].idxmax(axis=1).str.removeprefix("weight_")
        return _records(t.rename(columns={f"weight_{m}": m for m in MODELS}))

    monthly = ev.assign(month=ev["timestamp"].dt.to_period("M").astype(str))
    return {
        "by_location_lead": summarise(["target_variable", "lead_time_hours", "location"]),
        "by_location_season": summarise(["target_variable", "lead_time_hours", "location", "season"]),
        "by_regime": summarise(["target_variable", "lead_time_hours", "weather_regime"]),
        "monthly": summarise(["target_variable", "lead_time_hours", "location", "month"], monthly),
        "fallback_levels": _records(
            ev.groupby(["target_variable", "lead_time_hours"])["fallback_level"].value_counts(normalize=True)
            .rename("share").reset_index()
        ),
    }


def build_skill(ev: pd.DataFrame) -> dict:
    sources = {**MEMBER_SOURCES, "equal_mean": "equal_mean", "blended": "blended",
               **{f"{cfg}.{method}": candidate_column(cfg, method) for cfg, method in CANDIDATES}}
    out = {}
    for name, by in {
        "by_variable_lead": ["target_variable", "lead_time_hours"],
        "by_location": ["target_variable", "lead_time_hours", "location"],
        "by_season": ["target_variable", "lead_time_hours", "season"],
        "by_regime": ["target_variable", "lead_time_hours", "weather_regime"],
    }.items():
        out[name] = _records(add_skill_scores(skill_table(ev, sources, by), by, list(MEMBER_SOURCES)))
    return out


def build_extremes(ev: pd.DataFrame, scales: dict) -> dict:
    sources = {
        **{m: ev[f"{m}_forecast"] >= ev["event_threshold"] for m in MODELS},
        "blended_raw": ev["blended"] >= ev["event_threshold"],
        "guidance": ev["guidance_event"],
    }
    events = ev[ev["guidance_event"] | (ev["observed_event"] == True)]  # noqa: E712
    top = (
        events.sort_values("event_probability", ascending=False)
        .groupby(["target_variable", "location"]).head(15)
        .sort_values("timestamp")
    )
    return {
        "verification": _records(verify_events(ev, sources)),
        "scales": [{"target_variable": v, "lead_time_hours": l, "scale": s} for (v, l), s in scales.items()],
        "event_names": EVENT_NAMES,
        "notable_events": _records(top[[
            "timestamp", "location", "target_variable", "lead_time_hours", "blended", "actual_value",
            "event_threshold", "guidance_threshold", "event_probability", "guidance_event", "observed_event",
        ]]),
    }


def default_event(ev: pd.DataFrame) -> dict | None:
    """Dashboard opens on the most confident correctly-forecast heavy-rain event."""
    hits = ev[(ev["target_variable"] == "precipitation_mm") & (ev["lead_time_hours"] == 12)
              & ev["guidance_event"] & (ev["observed_event"] == True)]  # noqa: E712
    if hits.empty:
        return None
    top = hits.sort_values(["event_probability", "blended"]).iloc[-1]
    return {"issue_time": str(top["timestamp"]), "location": top["location"]}


def run(retrain: bool = False) -> dict:
    t0 = time.time()
    _log("Stage 1/7  forecasts")
    archive = load_archive(retrain)

    _log("Stage 2/7  weather regimes (train-period calibration)")
    master = build_master_dataset()
    thresholds = training_thresholds(master)
    archive = archive.merge(build_regimes(master), on=["timestamp", "location"], how="left")

    _log(f"Stage 3/7  rolling-origin adaptive blending: {len(CONFIGS)} configs x {len(METHODS)} methods")
    blended, params = blend_all_configs(archive)
    blended["equal_mean"] = blended[FORECAST_COLUMNS].mean(axis=1)

    _log("Stage 4/7  per-(variable, lead) configuration + method selection on 2024")
    hindcast_mask = blended["timestamp"] < config.TEST_START
    selection = select_candidates(blended[hindcast_mask])
    blended = apply_selection(blended, params, selection)
    del params
    blended = attach_thresholds(blended, thresholds)

    _log("Stage 5/7  extreme guidance tuning (2024) and application")
    scales = tune_scales(blended[hindcast_mask])
    blended = apply_guidance(blended, scales)
    ev = blended[blended["timestamp"] >= config.TEST_START].copy()

    _log("Stage 6/7  2025 evaluation")
    skill = build_skill(ev)
    extremes = build_extremes(ev, scales)
    weights = build_weight_maps(ev)

    _log("Stage 7/7  export")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    export_cols = [
        "timestamp", "location", "latitude", "longitude", "season", "weather_regime",
        "target_variable", "lead_time_hours", *FORECAST_COLUMNS, "equal_mean", "blended", "actual_value",
        "blend_config", "blend_method", "fallback_level", "n_history", *(f"weight_{m}" for m in MODELS),
        *(f"bias_{m}" for m in MODELS), "event_threshold", "guidance_threshold",
        "event_probability", "guidance_event", "observed_event",
    ]
    ev[export_cols].to_csv(ARTIFACTS_DIR / "forecasts.csv", index=False, float_format="%.4f")
    headline = [
        r for r in skill["by_variable_lead"] if r["source"] in ("blended", *MODELS, "equal_mean")
    ]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime_seconds": round(time.time() - t0, 1),
        "evaluation_period": [str(config.TEST_START), str(config.TEST_END)],
        "hindcast_period": [str(config.HINDCAST_START), str(config.HINDCAST_END)],
        "weights_update_frequency": "monthly (expanding window)",
        "models": MODEL_LABELS,
        "methods": list(METHODS),
        "configs": {k: {"levels": [name for name, _ in v["levels"]], "bias_correct": v["bias_correct"]} for k, v in CONFIGS.items()},
        "selected_methods": [
            {"target_variable": v, "lead_time_hours": l, "config": c, "method": m} for (v, l), (c, m) in selection.items()
        ],
        "locations": _records(ev.groupby("location")[["latitude", "longitude"]].first().reset_index()),
        "variables": config.TARGET_VARIABLES,
        "lead_times_hours": config.LEAD_TIMES_HOURS,
        "rows": len(ev),
        "default_view": default_event(ev),
        "headline_skill": headline,
    }
    for name, payload in {"manifest": manifest, "skill": skill, "weights": weights, "extremes": extremes}.items():
        (ARTIFACTS_DIR / f"{name}.json").write_text(json.dumps(payload, indent=1, default=str))

    print_summary(skill, extremes, selection)
    _log(f"Done in {time.time() - t0:.0f}s -> {ARTIFACTS_DIR}")
    return manifest


def print_summary(skill: dict, extremes: dict, selection: dict) -> None:
    t = pd.DataFrame(skill["by_variable_lead"])
    pivot = t.pivot_table(index=["target_variable", "lead_time_hours"], columns="source", values="mae")
    cols = [*MODELS, "equal_mean", "blended"]
    print("\n=== 2025 MAE by source (lower is better) ===")
    print(pivot[cols].round(4).to_string())
    blended = t[t["source"] == "blended"].set_index(["target_variable", "lead_time_hours"])["mae_skill_pct"]
    print("\n=== Blended skill vs best individual model (MAE, %) ===")
    print(blended.round(2).to_string())
    print("\nSelected (config.method):", {f"{v}/{l}h": ".".join(m) for (v, l), m in selection.items()})
    v = pd.DataFrame(extremes["verification"])
    print("\n=== Extreme events 2025: CSI ===")
    print(v.pivot_table(index=["event", "lead_time_hours"], columns="source", values="csi").round(3).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--retrain", action="store_true", help="retrain all forecast models first")
    run(parser.parse_args().retrain)


if __name__ == "__main__":
    main()
