# Data schema

## Inputs: `data/*_era5_2021_2025_clean.csv`

One file per location, hourly, 2021-01-01 00:00 → 2025-12-31 23:00 (43,824 rows each).

| Column | Unit | Notes |
|---|---|---|
| `timestamp` | UTC | hourly, no gaps (validated) |
| `location`, `latitude`, `longitude` | — | constant per file |
| `temperature_2m_c` | °C | 2 m air temperature |
| `precipitation_mm` | mm/h | ≥ 0 |
| `u10`, `v10` | m/s | 10 m wind components |
| `wind_speed_10m` | m/s | √(u10² + v10²), validated |
| `season` | — | Winter (DJF), Summer (MAM), Monsoon (JJAS), Post-Monsoon (ON) |

## Forecast archive: `data/processed/lead_time_targets.csv`

Written by `python -m src.models.generate_forecasts`. It is in long format, with one row per
(timestamp, location, lead_time_hours, target_variable). `timestamp` is the
**issue time**, and the forecast is valid at `timestamp + lead_time_hours`.

| Column | Notes |
|---|---|
| `model_a_forecast` | Persistence |
| `model_b_forecast` | Random Forest |
| `ai_model_forecast` | Gradient-boosted trees |
| `actual_value` | ERA5 observation at valid time (NaN past the end of data) |

Forecast columns are filled for 2024 (hindcast run) and 2025 (operational run)
only. Earlier rows are training data and keep NaN.

## Workflow artifacts: `data/processed/artifacts/`

Written by `python -m src.workflow`, and read by the API.

### `forecasts.csv`: every 2025 blended forecast

Archive columns plus:

| Column | Notes |
|---|---|
| `weather_regime` | Regime at issue time (train-calibrated) |
| `equal_mean` | Unweighted mean of the members (baseline) |
| `blended` | WEAVE adaptive blend |
| `blend_config`, `blend_method` | Candidate selected for this variable/lead on the 2024 hindcast |
| `fallback_level` | Conditioning level the weights came from |
| `n_history` | Verified cases behind the weights |
| `weight_<model>` | Blend weights (sum to 1) |
| `bias_<model>` | Mean error removed before blending (0 when the configuration has no bias correction) |
| `event_threshold` | Location × season p95 for this variable |
| `guidance_threshold` | `scale × event_threshold` (CSI-tuned) |
| `event_probability` | Skill-weighted share of members above the guidance threshold |
| `guidance_event`, `observed_event` | Forecast and observed extreme flags |

### JSON artifacts

| File | Contents |
|---|---|
| `manifest.json` | Run metadata, periods, locations, selected candidate per variable/lead, default issue time |
| `skill.json` | MAE / RMSE / bias / `mae_skill_pct` for each source (members, simple mean, blend, all 12 candidates), by variable·lead, location, season and regime |
| `weights.json` | Mean weights and dominant model by location·lead, location·season, regime and month, plus the share of each fallback level |
| `extremes.json` | POD / FAR / CSI / frequency bias per event and source, tuned scales, notable events |
