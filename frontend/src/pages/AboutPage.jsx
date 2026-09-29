import { Link } from "react-router-dom";
import { useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import { Page, Rise, Stagger } from "../components/Motion";
import PageHeader from "../components/PageHeader";
import { LIVE_MODELS } from "../format";

const ALIGNMENT = [
  {
    need: "Physical NWP, ensemble and AI/ML forecasts may each have strengths",
    how: "Five live members: three physics models (ECMWF IFS, NCEP GFS, DWD ICON), the ECMWF 51-member ensemble mean, and ECMWF's AI model AIFS.",
    to: "/forecast",
  },
  {
    need: "Adaptive weights from historical skill, lead time, region, season and weather regime",
    how: "Weights are learned per place from 120 days of verified forecasts, separately for each day ahead (0–7), then conditioned on season, weather regime and hour of day.",
    to: "/weights",
  },
  {
    need: "Dynamically blended forecast for rainfall, temperature and wind",
    how: "Hourly blend for 8 days at any place in India, plus a 1.5° blended field over the whole country, refreshed automatically.",
    to: "/",
  },
  {
    need: "Model weight maps by region / lead time",
    how: "Regional map of the most-trusted model for each day ahead, and a city × lead-day grid of the weights.",
    to: "/weights",
  },
  {
    need: "Improved skill vs individual models",
    how: "Every place's blend is scored on 21 days it never trained on or selected from, against each model and a simple average.",
    to: "/performance",
  },
  {
    need: "Extreme guidance: heavy rainfall, heat wave, high wind",
    how: "IMD rainfall categories and heat-wave criteria on the blend, plus the ensemble's probability, plus official NDMA/IMD warnings.",
    to: "/extremes",
  },
  {
    need: "Operational workflow for routine blending",
    how: "A background refresh cycle every 20 minutes, a rate-safe data layer, a JSON API, and this dashboard.",
    to: "/operations",
  },
];

function AboutPage() {
  const models = useApi("/live/models");
  const meta = useApi("/meta");
  return (
    <>
      <PageHeader eyebrow="METHOD & DATA" title="How WEAVE works" />
      <Page>
        <section className="hero hero--compact">
          <div className="hero__text">
            <h2>The problem</h2>
            <p>
              Forecast systems perform differently depending on region, season, lead time and weather situation. WEAVE learns
              where and when each one is reliable and blends them with adaptive weights, so the combined forecast is better than
              any single model and extreme weather is flagged earlier.
            </p>
          </div>
        </section>

        <DashboardCard title="Problem statement → WEAVE" icon="task_alt" subtitle="Every requirement, where to see it">
          <Stagger as="ol" className="alignment">
            {ALIGNMENT.map((a) => (
              <Rise as="li" key={a.need}>
                <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
                <div><strong>{a.need}</strong><p>{a.how}</p></div>
                <Link to={a.to}>See it →</Link>
              </Rise>
            ))}
          </Stagger>
        </DashboardCard>

        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Live blending, step by step" icon="bolt">
              <ol className="prose-list">
                <li><strong>Skill history.</strong> Open-Meteo archives what each model forecast 0–7 days ahead. WEAVE pairs 120 days of those forecasts with ERA5 reanalysis at the place.</li>
                <li><strong>Candidates.</strong> 15 weighting schemes: equal, inverse-MAE, inverse-MSE, least-squares stacking and best single model, each with regime-only, bias-corrected or hour-of-day conditioning.</li>
                <li><strong>Honest selection.</strong> Candidates are fitted on the oldest days, chosen on the next 21 days and scored on the latest 21 days. That last score is what the Performance page reports, because the model never saw those days.</li>
                <li><strong>Blend.</strong> The chosen weights combine the latest runs. A model missing an hour is dropped and the rest renormalised; nothing is filled in.</li>
                <li><strong>Words and warnings.</strong> Daily summaries, IMD heat-wave and rainfall categories, and ensemble probabilities are computed from the blended numbers.</li>
              </ol>
            </DashboardCard>
            <DashboardCard title="What we tested and kept (or didn’t)" icon="science">
              <ul className="notes">
                <li><strong>More models is not automatically better.</strong> Adding UK Met Office, JMA and GEM as members left held-out blend error flat or worse (temperature −0.6%, rain +0.4%, wind −0.2% median change), so they are not used.</li>
                <li><strong>Longer history helps.</strong> 120 days with 21-day windows beat 75 days with 14-day windows (temperature and wind beat the best single model in 24/24 vs 20/24 test cases).</li>
                <li><strong>Rainfall is the hard one.</strong> Blending often only ties the best single model for rain. Turning off bias correction for rain was tested and made it worse, so the site reports the numbers as they are.</li>
                <li><strong>2025 replay models</strong> were tuned on 2023 only (never 2024–25), and a model that simply predicts “0 mm” for rain was rejected even though it scored a lower error.</li>
              </ul>
            </DashboardCard>
            <DashboardCard title="Limitations" icon="report">
              <ul className="notes">
                <li>ERA5 is published about 6 days late, so weights learn from forecasts that verified up to a week ago.</li>
                <li>Values represent a model grid cell (about 9–28 km), not a single weather station.</li>
                <li>Grid-map weights are borrowed from the nearest verified cities and have no local bias correction. City pages have both.</li>
                <li>“Normal” for heat waves is the ERA5 average of the last 2 years, not IMD’s 30-year station normals. IMD’s coastal heat-wave rule isn’t applied.</li>
                <li>Official warnings are relayed verbatim from NDMA SACHET. WEAVE’s own guidance never overrides them.</li>
              </ul>
            </DashboardCard>
          </div>
          <aside className="dashboard-grid__side">
            <DashboardCard title="Data sources" icon="database">
              <ul className="source-list">
                {LIVE_MODELS.map((m) => (
                  <li key={m.key}>
                    <i className="swatch" style={{ background: m.color }} /><strong>{m.label}</strong> <span className="muted">{m.kind} · {m.about}</span>
                    {models.data?.runs?.[m.key]?.initialised && <small className="muted"> · run {models.data.runs[m.key].initialised.slice(5, 16).replace("T", " ")} UTC</small>}
                  </li>
                ))}
                <li><strong>ERA5</strong> <span className="muted">reanalysis (truth), Copernicus Climate Change Service</span></li>
                <li><strong>NDMA SACHET</strong> <span className="muted">official CAP warnings from IMD, CWC and state authorities (public domain)</span></li>
                <li><strong>India boundary</strong> <span className="muted">Survey of India claim, via datameet (CC-0)</span></li>
                <li><strong>Geocoding</strong> <span className="muted">Open-Meteo / GeoNames</span></li>
                <li><strong>Basemap</strong> <span className="muted">© OpenStreetMap contributors</span></li>
              </ul>
              <p className="card-caption">Weather data by <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a> (CC BY 4.0, non-commercial tier).</p>
            </DashboardCard>
            <DashboardCard title="Research archive" icon="history" subtitle="2025 replay, 5 Maharashtra sites">
              <p className="card-caption">
                The original experiment: three trained models (persistence, random forest, gradient boosting) verified on every hour of 2025.
                {meta.data && ` Last rebuilt ${meta.data.generated_at.slice(0, 16).replace("T", " ")} UTC.`} <Link to="/historical">Open the replay →</Link>
              </p>
            </DashboardCard>
          </aside>
        </div>
      </Page>
    </>
  );
}

export default AboutPage;
