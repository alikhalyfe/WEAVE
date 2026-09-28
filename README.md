# Adaptive Weather Forecast Blending

AI + NWP based adaptive weather forecast blending system.

## Project Goal

Combine multiple weather forecast models using adaptive weights based on:

- Region
- Forecast lead time
- Season
- Weather regime
- Historical model performance

## Architecture

Forecast Models
       ↓
Data Pipeline
       ↓
Weather Regime Classification
       ↓
Adaptive Weight Engine
       ↓
Blended Forecast
       ↓
Evaluation
       ↓
Dashboard

## Team Modules

| Module | Owner |
|---|---|
| Data Pipeline | Member 1 |
| Adaptive Blending | Member 2 |
| Weather Regime | Member 3 |
| Evaluation | Member 4 |
| Dashboard | Member 5 |

## Project Structure

- `data/` - datasets
- `src/data_pipeline/` - data preprocessing
- `src/regime/` - weather regime classification
- `src/blending/` - adaptive model weighting and blending
- `src/evaluation/` - evaluation metrics
- `src/api/` - backend/API
- `dashboard/` - frontend
- `tests/` - tests
- `docs/` - project documentation