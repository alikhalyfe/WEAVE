<p align="center"><img src="frontend/public/logo-192.png" width="96" alt="WEAVE logo"></p>

# WEAVE: Adaptive AI–NWP Forecast Blending for India

WEAVE blends five forecast systems into one forecast for any place in India:

- **Physics-based NWP:** ECMWF IFS, NCEP GFS and DWD ICON.
- **Ensemble:** the ECMWF 51-member ensemble.
- **AI model:** ECMWF AIFS.

Adaptive weights are learned from each model's **verified skill** at that place and conditioned on **lead time, region, season, weather regime and hour of day**. The output is an optimised forecast for **rainfall, temperature and wind**, with **heat-wave, heavy-rain and high-wind guidance** and **official IMD/NDMA warnings**, all in plain language on a live dashboard.

## The problem statement, point by point

| Requirement | Where it lives |
|---|---|
| Physical NWP, ensemble and AI/ML forecasts may each have strengths | 5 live members: IFS, GFS, ICON (NWP), ECMWF ENS mean (ensemble), AIFS (AI). `src/live/openmeteo.py` |
| Adaptive weights from historical skill, lead time, region, season, weather regime | Per place: 120 days of archived forecasts scored against ERA5. Weights per lead day 0–7, conditioned on season, weather regime and hour. `src/live/engine.py`, `src/blending/operational.py` |
| **Dynamically blended forecast** (rain, temperature, wind) | Hourly 8-day blend for any place, a 1.5° blended field over all of India, and a plain-language daily outlook. *Overview* and *Forecast* pages |
| **Model weight maps** by region and lead time | Regional most-trusted-model map for each lead day, plus a city × lead-day grid. *Model Weights* page, map layer on *Overview* |
| **Improved forecast skill** vs individual models | Every blend is scored on held-out days it never trained on or selected from. *Performance* page |
| **Extreme weather guidance** (heavy rain, heat wave, high wind) | IMD rainfall categories and heat-wave criteria on the blend, 51-member ensemble probabilities, and official NDMA SACHET warnings. *Warnings* page |
| **Operational workflow** (automated routine blending) | A background refresh every 20 min, a rate-safe data layer and a JSON API. *Operations* page; replay pipeline via `python -m src.workflow` |

## What you see

- **Overview:**
  - India forecast map on a 1.5° grid, in IMD rainfall categories and temperature and wind bands, inside the Survey of India boundary.
  - Day scrubber with play, and a "most-trusted model" layer.
  - Official warnings, the WEAVE hazard outlook, and every tracked city's day in words.
- **Forecast:** search any Indian place.
  - The week in plain language: "Light rain, around 4 mm. Chance of rain 92%. A light breeze, up to 11 km/h."
  - Hazard chips and official warnings within 150 km.
  - The detail: 7-day chart of all 5 models plus the blend, ensemble ranges, weights per day ahead, the held-out track record, and accuracy by lead day.
- **Model Weights:** the regional weight map and the city × lead-day dominant-model grid.
- **Performance:** blend vs best single model, per city and lead day, plus the 2025 replay skill.
- **Warnings:** official NDMA SACHET warnings (IMD, CWC, state SDMAs, relayed verbatim), WEAVE's heat-wave, heavy-rain and high-wind signals, and their verification.
- **Operations:** the pipeline, refresh loop, API budget and data freshness.
- **2025 Replay / Blend Tool / Method & Data:** the research archive, manual blending, and the method, sources and limitations.

## How the live blend works

1. **Skill history.** Open-Meteo archives what each model forecast 0–7 days ahead. WEAVE pairs 120 days of those forecasts with ERA5 at the place.
2. **Honest selection.** 15 candidates are tried: 5 weighting methods (equal, inverse-MAE, inverse-MSE, NNLS stacking, best single model) × 3 conditioning setups (regime; regime with bias correction; hour of day with bias correction).
   - They're fitted on the oldest days, **chosen** on the next 21 days, and **scored** on the latest 21 days.
   - Only that final score is reported.
3. **Blend.** The chosen weights combine the latest runs. A model missing an hour is dropped and the rest renormalised; nothing is filled in.
4. **Words and warnings.**
   - IMD rain categories: heavy ≥ 64.5 mm/day.
   - IMD heat-wave criteria: ≥ 40 °C in the plains, or ≥ 30 °C in the hills, and at least 4.5 °C above normal.
   - Beaufort wind wording, and chance of rain = share of the 51 ensemble members with ≥ 1 mm.
   - **Warning** = the blend meets the rule; **watch** = at least 30% of ensemble members do.
5. **India grid.** 124 points inside the boundary, blended with weights borrowed from the nearest verified cities (inverse distance). That is the regional weight map.

### Live results (24 cities × 8 lead days, held-out window, five members)

| Variable | Blend beats best single model | Median gain vs best model | Median gain vs simple average |
|---|---|---|---|
| Temperature | 154 / 192 (80%) | **+17.6%** | +23.8% |
| Wind | 165 / 192 (86%) | **+11.9%** | +7.5% |
| Rainfall | 75 / 192 (39%) | −2.7% | +3.4% |

Rainfall is the honest weak spot: it's zero-inflated, and the scoring window covered the monsoon withdrawal.

### Tested and rejected

- **UK Met Office, JMA and GEM as extra members.** Held-out blend error changed by −0.6% (temperature), +0.4% (rain) and −0.2% (wind) at the median. That's no gain, so they're not used.
- **Rain without bias correction.** It made rain worse (49/192 wins).
- **Hourly "unusual" thresholds.** They flagged ordinary afternoon peaks, so extremes are judged per day.

## 2025 replay (research archive, fully out-of-sample)

Three trained members at 5 Maharashtra ERA5 points: persistence, random forest and gradient boosting.

- **Features:** the "same hour yesterday" lag (18 h), 24-hour rolling statistics, and cyclic time features.
- **Tuning:** gradient-boosting hyperparameters were chosen on 2023 only (`src/models/tuning.py`). A candidate that predicted a constant 0 mm of rain scored a lower MAE but was rejected as degenerate.
- **Blend settings:** chosen on a 2024 hindcast, then frozen for 2025.

| Variable | Lead | Persistence | Random Forest | AI (GBT) | **WEAVE blend** | vs best model |
|---|---|---|---|---|---|---|
| Rainfall (mm/h) | 6h | 0.2083 | 0.1810 | 0.1782 | **0.1750** | **+1.8%** |
| | 12h | 0.2369 | 0.2008 | 0.1951 | **0.1912** | **+2.0%** |
| | 24h | 0.2307 | 0.2063 | 0.2036 | **0.1958** | **+3.9%** |
| Temperature (°C) | 6h | 3.7848 | 0.7130 | 0.6427 | 0.6431 | −0.1% |
| | 12h | 5.3993 | 0.7773 | 0.7339 | 0.7347 | −0.1% |
| | 24h | 0.8301 | 0.8114 | 0.7998 | **0.7958** | **+0.5%** |
| Wind (m/s) | 6h | 0.8783 | 0.5223 | 0.5087 | 0.5097 | −0.2% |
| | 12h | 1.0030 | 0.5765 | 0.5646 | 0.5654 | −0.1% |
| | 24h | 0.6747 | 0.6192 | 0.6150 | **0.6083** | **+1.1%** |

Tuning cut temperature 6h error by 15% (0.756 → 0.643 °C). The tuned AI member is now so strong that for temperature and wind the blend mostly defers to it, which is why the margin over the best single model is near zero. Rain at 12 and 24 h got slightly worse in absolute terms after tuning.

Extreme events at 6h (CSI, higher is better):

| Event | Before tuning | After tuning |
|---|---|---|
| Heat | 0.50 | **0.65** |
| Heavy rain | 0.19 | **0.20** |
| High wind | 0.35 | **0.39** |

## Run it

```bash
python -m venv venv && venv/Scripts/activate      # Windows (source venv/bin/activate elsewhere)
pip install -r requirements.txt
uvicorn src.api.main:app                          # API + background refresh on :8000

cd frontend && npm install && npm run dev         # dashboard on :5173 (proxies /api)
# or npm run build: the API then serves the dashboard itself at :8000
```

- No keys and no training are needed for live mode. The committed `data/artifacts/` serve the replay.
- Rebuild the replay with `python -m src.models.tuning && python -m src.workflow --retrain` (about 15 min).
- Tests: `pytest` runs 94 tests, including live mode against a mocked Open-Meteo, SACHET parsing, IMD rules, leakage guards and the API.

## Deploy (Render API + Vercel frontend)

1. **Render:** New → Blueprint → this repo (`render.yaml`). Set `ALLOWED_ORIGINS` to the Vercel URL.
2. **Vercel:** import with root directory `frontend`, and set `VITE_API_BASE=https://<render-service>.onrender.com`.
3. **Cold starts:** the free Render tier sleeps. The first visit wakes it (about 30–60 s) and the refresher then warms the 24 cities and the grid.

**Fair use.** Open-Meteo's free tier is non-commercial, with a budget of 600 units per minute, 5,000 per hour and 10,000 per day. WEAVE weighs every request with Open-Meteo's own formula, waits out the per-minute limit, and refuses cleanly before the hourly or daily limit. A steady day uses roughly 6,000 units.

## Data sources and licences

| Source | Licence |
|---|---|
| Open-Meteo: ECMWF IFS, ENS and AIFS, NOAA GFS, DWD ICON, ERA5 | CC BY 4.0 |
| NDMA SACHET, official warnings | Public domain |
| India boundary: datameet `india-composite` (Survey of India claim) | CC-0 |
| Basemap | © OpenStreetMap contributors |

## Project structure

| Path | Contents |
|---|---|
| `src/live/` | Open-Meteo client and budget, cache, engine, outlook/IMD rules, SACHET alerts, India grid, refresh service |
| `src/blending/` | Weight engine (inverse error, NNLS, best member), operational blender |
| `src/models/` | Replay members, leak-free tuning, forecast generation |
| `src/evaluation/`, `src/regime/`, `src/data_pipeline/`, `ai/` | Verification, regimes, ERA5 pipeline |
| `src/api/main.py` | FastAPI: `/api/live/*`, replay endpoints, `POST /api/blend`, SPA |
| `frontend/` | React + Vite: routed pages, Leaflet maps, Motion animations |
| `data/geo/`, `data/artifacts/` | India boundary; published replay artifacts |

## Limitations

- **Grid cells, not stations:** values are for a model grid cell (about 9–28 km). ERA5 truth lags about 6 days.
- **Grid-map weights are borrowed:** they come from the nearest verified cities and have no local bias correction. City pages have both.
- **Heat-wave "normal":** it is the ERA5 average of the last 2 years, not IMD's 30-year station normals, and the coastal heat-wave rule isn't applied.
- **Official warnings come first:** they're relayed verbatim, and WEAVE's guidance never overrides them.
