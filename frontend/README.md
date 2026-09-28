# WEAVE dashboard

React 19 + Vite. All data comes from the WEAVE API (`src/api/main.py`); there is no mock data.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
npm run build    # dist/ is then served by the API itself at /
npm run lint
```

Start the API first, from the repo root: `python -m src.workflow` (once), then `uvicorn src.api.main:app`.

| Panel | Source |
|---|---|
| Forecast cards, weight map donuts, alerts | `GET /api/snapshot` |
| Forecast comparison chart | `GET /api/series` |
| Year timeline | `GET /api/daily` |
| Forecast skill | `GET /api/skill` |
| Weight grid | `GET /api/weights` |
| Extreme event skill | `GET /api/extremes` |
| Blend new forecasts | `POST /api/blend` |
| Workflow | `GET /api/meta` |

The selection (location, variable, lead, issue time) lives in the URL, so any view can be shared as a link.
Charts are hand-built SVG with no chart library. Series colours come from a CVD-validated categorical palette, and every chart has a legend and a table view.
