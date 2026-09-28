import { Link } from "react-router-dom";
import { useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import { Page, Rise, Stagger } from "../components/Motion";
import PageHeader from "../components/PageHeader";
import WorkflowCard from "../components/WorkflowCard";
import { LIVE_MODELS } from "../format";

const OUTCOMES = [
  ["Dynamically blended forecast", "Four live models combined per city, variable and lead day, with weights re-learned from verified history.", "/forecast"],
  ["Model weight maps", "Which model the blend trusts at each city and lead day, on a map and a grid.", "/weights"],
  ["Improved forecast skill", "Blend vs the best single model, scored on held-out days, city by city.", "/performance"],
  ["Extreme weather guidance", "Heavy rain, heat and high-wind signals against each city’s own 95th percentile, with verification.", "/extremes"],
  ["Operational workflow", "Automatic refresh from new model runs; historical pipeline via python -m src.workflow.", "/historical"],
];

function AboutPage() {
  const models = useApi("/live/models");
  const meta = useApi("/meta");
  return (
    <>
      <PageHeader eyebrow="METHOD & DATA" title="How WEAVE works" />
      <Page>
        <Stagger className="outcome-grid">
          {OUTCOMES.map(([title, text, to]) => (
            <Rise key={title} className="dashboard-card outcome">
              <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
              <strong>{title}</strong>
              <p>{text}</p>
              <Link to={to}>Open →</Link>
            </Rise>
          ))}
        </Stagger>

        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Live mode, step by step" icon="bolt">
              <ol className="prose-list">
                <li><strong>Members.</strong> The latest runs of ECMWF IFS, NCEP GFS and DWD ICON (physics-based NWP) and ECMWF AIFS (machine-learned), hourly for about 7 days.</li>
                <li><strong>Skill history.</strong> Open-Meteo archives what each model forecast 0–7 days ahead. WEAVE compares 120 days of those archived forecasts with ERA5 reanalysis at the same place.</li>
                <li><strong>Honest windows.</strong> The oldest days fit every candidate weighting (4 weighted methods, plus a best-single-model option, × 3 conditioning setups). The next 21 days choose one. The latest 21 days score it. That score is what the Performance page shows.</li>
                <li><strong>Adaptive weights.</strong> Weights depend on lead day, and within it on season, weather regime and hour of day, falling back to broader groups when data is thin. A model with no forecast for an hour is dropped and the others renormalised.</li>
                <li><strong>Extremes.</strong> An hour is flagged when the blend reaches the 95th percentile of that season in the place’s last 12 months of ERA5. The agreement score is the weighted share of models that also reach it.</li>
              </ol>
            </DashboardCard>
            <DashboardCard title="Limitations" icon="report">
              <ul className="notes">
                <li>ERA5 is published about 6 days late, so weights learn from forecasts that verified up to a week ago.</li>
                <li>Values are for the model grid cell (about 9–28 km), not a street-level station.</li>
                <li>Rainfall is hard to blend: it often only ties the best single model. The Performance page shows this rather than hiding it.</li>
                <li>Heat events are hourly 95th-percentile exceedances, not IMD’s official heat-wave definition.</li>
                <li>Open-Meteo’s free tier is for non-commercial use.</li>
              </ul>
            </DashboardCard>
          </div>
          <aside className="dashboard-grid__side">
            <DashboardCard title="Data sources" icon="database">
              <ul className="source-list">
                {LIVE_MODELS.map((m) => (
                  <li key={m.key}>
                    <i className="swatch" style={{ background: m.color }} /><strong>{m.label}</strong> <span className="muted">{m.kind}</span>
                    {models.data?.runs?.[m.key]?.initialised && <small className="muted"> · latest run {models.data.runs[m.key].initialised.slice(0, 16).replace("T", " ")} UTC</small>}
                  </li>
                ))}
                <li><strong>ERA5</strong> <span className="muted">reanalysis, Copernicus Climate Change Service</span></li>
                <li><strong>Geocoding</strong> <span className="muted">Open-Meteo / GeoNames</span></li>
                <li><strong>Basemap</strong> <span className="muted">© OpenStreetMap contributors</span></li>
              </ul>
              <p className="card-caption">Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a>, licensed CC BY 4.0.</p>
            </DashboardCard>
            <WorkflowCard meta={meta.data} />
          </aside>
        </div>
      </Page>
    </>
  );
}

export default AboutPage;
