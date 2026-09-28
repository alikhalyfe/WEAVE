# WEAVE frontend

React 19 + Vite + react-router + Motion + Leaflet. Every number comes from the WEAVE API; there is no mock data.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api -> http://127.0.0.1:8000
npm run build    # dist/ (served by the API at /, or deployed to Vercel)
npm run lint
```

Hosted separately (Vercel), set `VITE_API_BASE` to the API origin (see `.env.example`). `vercel.json` rewrites every route to `index.html`.

| Route | Page | Data |
|---|---|---|
| `/` | Overview: India map, extreme days ahead, city table | `GET /api/live/cities` (polls while cities compute) |
| `/forecast?name&lat&lon` | Any Indian place: 7-day chart, daily outlook, weights per lead day, track record, skill | `GET /api/live/forecast` |
| `/weights` | Most-trusted model per city and lead day (map + grid) | `GET /api/live/cities` |
| `/performance` | Blend vs best single model; 2025 replay skill | `/api/live/cities`, `/api/skill` |
| `/extremes` | Live extreme days + verification; 2025 replay event skill | `/api/live/cities`, `/api/extremes` |
| `/blend` | Blend your own member values | `POST /api/blend` |
| `/historical` | 2025 replay dashboard | `/api/meta`, `/api/snapshot`, `/api/series`, … |
| `/about` | Method, data sources, attribution | `/api/live/models`, `/api/meta` |

Conventions:

- **Data provenance:** each page shows a *Live* or *Historical replay · 2025* badge. Loading shows skeletons, never placeholder numbers.
- **Colour:** series colours come from a CVD-validated categorical palette, and every chart has a legend and a table view.
- **Motion:** animations respect `prefers-reduced-motion`.
- **Times:** live pages show IST; the replay shows UTC.
