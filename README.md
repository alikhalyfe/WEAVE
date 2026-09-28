# WEAVE: Adaptive Weather Forecast Blending

A hybrid AI–NWP blending framework for India. WEAVE combines physics-based
numerical weather prediction (**ECMWF IFS, NCEP GFS, DWD ICON**) with a
machine-learned model (**ECMWF AIFS**) using **adaptive weights**. The weights
are learned from each model's verified skill and conditioned on **place, lead
time, season, weather regime and hour of day**. The output is an optimised
forecast for **rainfall, temperature and wind**, with **extreme-weather
guidance**, for any city or town in India.

It runs in two modes that share one blending engine:

| | **Live** | **2025 replay (research)** |
|---|---|---|
| Members | ECMWF IFS, NCEP GFS, DWD ICON (NWP) + ECMWF AIFS (AI) | Persistence, Random Forest, gradient boosting |
| Where | Any place in India (search), 24 tracked cities on the map | 5 Maharashtra ERA5 grid points |
| Leads | Days 0–7, hourly | 6 / 12 / 24 h |
| Truth | ERA5 (≈6-day lag) | ERA5 |
| Data | Open-Meteo, fetched on demand and cached | Committed artifacts in `data/artifacts/` |

## Expected outcomes → where they live

| Problem-statement outcome | Delivered by |
|---|---|
| **Dynamically blended forecast** | Live: `src/live/engine.py` blends the latest run of 4 models per place, variable and lead day. Replay: `src/blending/operational.py` does a rolling-origin blend of every 2025 forecast. |
| **Model weight maps** | *Model Weights* page: India map of the most-trusted model per city and lead day, plus a city × lead grid. Replay: map and grid by location, lead time and season. |
| **Improved forecast skill** | *Performance* page. Live: blend vs the best single model, scored on held-out days per city. Replay: 2025 MAE tables. |
| **Extreme weather guidance** | *Extreme Events* page: heavy-rain, heat and high-wind days against each place's own ERA5 95th percentile for the date, with model agreement and verification. |
| **Operational workflow** | Live refresh is automatic (cached, rate-budgeted Open-Meteo calls). Replay: `python -m src.workflow`. There is also a REST API and a blend tool. |

## How the live blend works

For each place (`src/live/engine.py`):

1. **Skill history.** Open-Meteo archives what each model forecast 0–7 days
   ahead. WEAVE pairs 120 days of those archived forecasts with ERA5 at the
   place.
2. **Honest windows.** The oldest days fit every candidate weighting: 5
   methods (equal, inverse-MAE, inverse-MSE, NNLS-optimal, best single model)
   × 3 conditioning setups (with and without bias correction, with and without
   hour-of-day). The next 21 days pick one candidate. The latest 21 days, never
   used for fitting or picking, **score** it. Those scores are what the site
   reports.
3. **Adaptive weights.** Weights are per lead day. Within each lead day they
   depend on season, weather regime (forecast by the members) and hour of day,
   falling back to broader groups when data is thin. A model with no forecast
   for an hour is dropped and the others renormalised; nothing is filled in.
4. **Extremes.** A day is extreme when the blended daily max temperature, rain
   total or max wind reaches the 95th percentile of the same ±15 days of year
   over the place's last 2 years of ERA5. Agreement is the weighted share of
   bias-corrected models that also reach it.

### Live results (24 cities × 8 lead days, held-out window 2–23 Sep 2026)

Blend MAE vs the best single model at each city and lead day:

| Variable | Blend beats best model | Median MAE reduction |
|---|---|---|
| Temperature | 154 / 192 (80%) | **+18.3%** |
| Wind speed | 174 / 192 (91%) | **+13.0%** |
| Rainfall | 77 / 192 (40%) | −2.6% |

Rainfall is the honest weak spot. It is zero-inflated and the scoring window
covered the monsoon withdrawal, so weights learned on wetter weeks transfer
poorly. Turning off bias correction for rain was tested and made it worse
(49/192), so all candidates stay and the site shows these numbers as they are.
Results refresh as the window rolls forward.

Live extreme-day check (day-1 forecasts, 480 city-days): heat POD 47% / FAR
21%; heavy rain POD 17% / FAR 78%; high wind 0 of 8 events detected. Extreme
days are rare, so treat these as a sanity check. The replay year below has the
statistically meaningful numbers.

## 2025 replay results (fully out-of-sample)

Models were trained on 2021–2024. Every blending choice was made on a 2024
hindcast and then frozen.

| Variable | Lead | Persistence | Random Forest | AI (GBT) | Simple mean | **WEAVE blend** | vs best model |
|---|---|---|---|---|---|---|---|
| Rainfall (mm/h) | 6h | 0.2083 | 0.1817 | 0.1785 | 0.1813 | **0.1766** | **+1.1%** |
| | 12h | 0.2369 | 0.1958 | 0.1898 | 0.1971 | **0.1880** | **+0.9%** |
| | 24h | 0.2307 | 0.2036 | 0.1991 | 0.2014 | **0.1933** | **+2.9%** |
| Temperature (°C) | 6h | 3.7848 | 0.7650 | 0.7794 | 1.4775 | **0.7563** | **+1.1%** |
| | 12h | 5.3993 | 0.7811 | 0.7594 | 1.9470 | 0.7611 | −0.2% |
| | 24h | 0.8301 | 0.8122 | 0.8125 | 0.7994 | **0.7992** | **+1.6%** |
| Wind (m/s) | 6h | 0.8783 | 0.5562 | 0.5640 | 0.6049 | **0.5383** | **+3.2%** |
| | 12h | 1.0030 | 0.5777 | 0.5779 | 0.6400 | **0.5676** | **+1.8%** |
| | 24h | 0.6747 | 0.6167 | 0.6243 | 0.6123 | **0.6120** | **+0.8%** |

Extreme events, 12h lead, critical success index: heavy rain 0.148 vs the best
raw model's 0.147; high wind **0.338 vs 0.213**; heat **0.627 vs 0.620**.

## Run it locally

```bash
python -m venv venv && venv/Scripts/activate      # Windows (source venv/bin/activate elsewhere)
pip install -r requirements.txt
uvicorn src.api.main:app                          # API on http://127.0.0.1:8000

cd frontend && npm install
npm run dev                                       # http://localhost:5173 (proxies /api)
```

No setup is needed for live mode: no key and no training. The committed
`data/artifacts/` serve the replay. To regenerate the replay, run
`python -m src.workflow` (about 2 min, or about 12 min with `--retrain`).

Tests: `pytest` runs 86 tests, including live mode against a mocked Open-Meteo,
leakage guards, blending, guidance and the API.

## Deploy (Render API + Vercel frontend)

1. **Render.** New → Blueprint → this repo. `render.yaml` defines the `weave-api`
   web service. Set `ALLOWED_ORIGINS` to the Vercel URL, e.g.
   `https://weave.vercel.app`.
2. **Vercel.** Import the repo with **root directory `frontend`**. Add the env var
   `VITE_API_BASE=https://<your-render-service>.onrender.com`.
   `frontend/vercel.json` handles SPA routing.
3. Open the Vercel URL. The first visit after the free Render instance sleeps
   takes about 30–60 s to wake. Each new city takes about 5–15 s the first time
   while WEAVE learns its model skill, then it's cached.

**Fair use.** Open-Meteo's free tier is non-commercial, with a budget of 600
units per minute, 5,000 per hour and 10,000 per day. Heavy requests count as
multiple units. WEAVE weighs every request with Open-Meteo's own formula,
waits out the per-minute limit, and returns a clear error rather than exceed
the hourly or daily budget. A new place costs about 145 units once, and cached
places are close to free. Attribution: *Weather data by Open-Meteo.com (CC BY
4.0)*, which is shown on every page.

## Project structure

| Path | Contents |
|---|---|
| `src/live/` | Open-Meteo client and budget, cache, live engine, city service |
| `src/blending/` | Weight engine (inverse error, NNLS), single-case and operational blenders |
| `src/regime/` | Vectorized regime classification |
| `src/evaluation/` | Metrics, skill tables, extreme-event verification and guidance |
| `src/models/`, `src/data_pipeline/`, `ai/` | Replay members, ERA5 pipeline, regime calibration |
| `src/workflow.py` | Replay workflow → `data/artifacts/` |
| `src/api/main.py` | FastAPI: `/api/live/*`, replay endpoints, `POST /api/blend`, SPA |
| `frontend/` | React + Vite: routed pages, Leaflet maps, Motion animations |
| `docs/` | Architecture, data schema |

## Limitations

- Values are for the model grid cell (about 9–28 km), not a street-level station.
- ERA5 is about 6 days behind, so weights learn from forecasts that verified up
  to a week ago.
- Live leads are whole days, because Open-Meteo archives forecasts by lead day.
- "Heat" means unusually hot for the date and place (daily-max 95th
  percentile), not IMD's official heat-wave criteria.
- Open-Meteo's free tier is non-commercial.

## Team

| Module | Owner |
|---|---|
| Data Pipeline | Member 1 |
| Adaptive Blending | Member 2 |
| Weather Regime | Member 3 |
| Evaluation | Member 4 |
| Dashboard | Member 5 |
