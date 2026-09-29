import { useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import { Bar, Page, Rise, SkeletonCard, Stagger } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import WorkflowCard from "../components/WorkflowCard";
import { LIVE_MODELS } from "../format";

const STAGES = [
  { icon: "cloud_download", title: "Fetch", text: `Latest runs of ${LIVE_MODELS.map((m) => m.short).join(", ")}, the 51-member ensemble, ERA5 truth and official warnings.` },
  { icon: "fact_check", title: "Verify", text: "Score every model's archived forecasts against ERA5, per place, variable and day ahead (120 days)." },
  { icon: "tune", title: "Learn weights", text: "Fit 15 candidate weightings, choose on one held-out window and score on a later one." },
  { icon: "merge", title: "Blend", text: "Combine the members with weights for the season, weather regime, hour and day ahead." },
  { icon: "crisis_alert", title: "Guide", text: "Flag heat waves, heavy rain and high wind (IMD-style rules + ensemble probabilities)." },
  { icon: "public", title: "Publish", text: "Refresh the India grid, city forecasts, weight maps and API for the dashboard." },
];

const minutes = (s) => (s == null ? "—" : s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`);
const hours = (s) => (s >= 86400 ? `${Math.round(s / 86400)} d` : s >= 3600 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 60)} min`);
const TTL_LABELS = {
  forecast: "Model forecasts", ensemble: "Ensemble members", grid: "India grid forecasts", previous_runs: "Archived forecasts (skill history)",
  era5: "ERA5 truth", climatology: "ERA5 climatology (thresholds)", geocode: "Place search", meta: "Model run times",
};

function OperationsPage() {
  const st = useApi("/live/status", { pollMs: 10000, poll: () => true });
  const meta = useApi("/meta");
  const s = st.data;

  return (
    <>
      <PageHeader eyebrow="OPERATIONS · ROUTINE BLENDING" title="Operational workflow" badge={<SourceBadge kind="live" detail="status refreshes every 10 s" />} />
      <Page>
        <Stagger className="pipeline" as="ol">
          {STAGES.map((stage, i) => (
            <Rise as="li" key={stage.title} className="pipeline__stage">
              <span className="pipeline__num">{i + 1}</span>
              <span className="material-symbols-outlined" aria-hidden="true">{stage.icon}</span>
              <strong>{stage.title}</strong>
              <p>{stage.text}</p>
            </Rise>
          ))}
        </Stagger>

        {!s ? <SkeletonCard lines={6} height={120} /> : (
          <div className="dashboard-grid">
            <div className="dashboard-grid__main">
              <DashboardCard title="Automatic refresh" icon="autorenew" subtitle="Runs inside the API process, with no cron job needed"
                action={<span className="card-tag">EVERY {Math.round(s.refresher.interval_seconds / 60)} MIN</span>}>
                <div className="ops-stats">
                  <div><span>Refresh cycles run</span><strong>{s.refresher.runs}</strong></div>
                  <div><span>Next cycle in</span><strong>{minutes(s.refresher.next_run_in_seconds)}</strong></div>
                  <div><span>Cities ready</span><strong>{s.cities.ready}/{s.cities.total}</strong></div>
                  <div><span>Places cached</span><strong>{s.places_cached}</strong></div>
                  <div><span>India grid</span><strong>{s.grid.status === "ready" ? `${s.grid.cells} cells` : s.grid.status}</strong></div>
                  <div><span>Official warnings</span><strong>{s.official_alerts.active ?? "—"}</strong></div>
                </div>
                {s.refresher.last_error && <p className="form-error">Last cycle error: {s.refresher.last_error}</p>}
                <p className="card-caption">
                  Each cycle re-blends any city older than 30 minutes and rebuilds the grid. Models publish new runs every 6–12 hours;
                  cached downloads are reused until then, so a cycle is cheap.
                </p>
              </DashboardCard>

              <DashboardCard title="Data freshness policy" icon="schedule" subtitle="How long each source is cached before re-downloading">
                <table className="data-table">
                  <thead><tr><th>Source</th><th>Refreshed every</th></tr></thead>
                  <tbody>
                    {Object.entries(s.ttl_seconds).map(([k, v]) => <tr key={k}><td>{TTL_LABELS[k] || k}</td><td>{hours(v)}</td></tr>)}
                    <tr><td>Official warnings (NDMA SACHET)</td><td>10 min</td></tr>
                  </tbody>
                </table>
              </DashboardCard>
            </div>

            <aside className="dashboard-grid__side">
              <DashboardCard title="Open-Meteo budget" icon="speed" subtitle={s.budget.note}>
                {["minute", "hour", "day"].map((w) => (
                  <div className="budget-row" key={w}>
                    <span>Per {w}</span>
                    <Bar value={s.budget.used[w]} max={s.budget.limits[w]} color={s.budget.used[w] / s.budget.limits[w] > 0.8 ? "#d03b3b" : "#4a3aa7"} />
                    <strong>{Math.round(s.budget.used[w])} / {s.budget.limits[w]}</strong>
                  </div>
                ))}
                <p className="card-caption">Free tier: 600 / 5,000 / 10,000 units. WEAVE waits out the minute limit and refuses new work past the hourly or daily budget, so it never gets blocked.</p>
              </DashboardCard>
              <WorkflowCard meta={meta.data} />
              <DashboardCard title="API" icon="api" subtitle="Everything on this site is available as JSON">
                <ul className="source-list">
                  {["/api/live/forecast?lat=…&lon=…", "/api/live/grid", "/api/live/cities", "/api/live/official-alerts", "/api/live/status", "POST /api/blend"].map((e) => <li key={e}><code>{e}</code></li>)}
                </ul>
                <p className="card-caption">Interactive documentation at <code>/docs</code> on the API server.</p>
              </DashboardCard>
            </aside>
          </div>
        )}
      </Page>
    </>
  );
}

export default OperationsPage;
