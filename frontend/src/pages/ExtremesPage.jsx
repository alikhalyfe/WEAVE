import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import ExtremeVerification from "../components/ExtremeVerification";
import IndiaGridMap from "../components/IndiaGridMap";
import { Page, SkeletonCard } from "../components/Motion";
import OfficialAlerts from "../components/OfficialAlerts";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import { HAZARD_ICON, LEVEL_STYLE, VARIABLES, ago, fmt, pct, placeUrl } from "../format";
import { useCities } from "../live";

/** Pool per-city day-1 verification (unusual days) into one contingency table. */
function pooled(ready, variable) {
  let obs = 0, fc = 0, hits = 0, cities = 0, days = 0;
  for (const c of ready) {
    const e = (c.summary.verification?.[variable] || []).find((x) => x.lead_day === 1);
    if (!e) continue;
    cities += 1;
    days += e.days;
    obs += e.observed_events;
    fc += e.forecast_events;
    hits += e.pod !== null ? Math.round(e.pod * e.observed_events) : 0;
  }
  return { cities, days, obs, fc, pod: obs ? hits / obs : null, far: fc ? (fc - hits) / fc : null, csi: obs + fc - hits ? hits / (obs + fc - hits) : null };
}

const RULES = [
  { type: "heat_wave", title: "Heat wave", text: "IMD criteria on the blended daily max: ≥ 40 °C in the plains (≥ 30 °C in the hills) and ≥ 4.5 °C above normal (severe ≥ 6.5 °C), or ≥ 45 °C outright." },
  { type: "heavy_rain", title: "Heavy rain", text: "IMD categories on the blended 24-hour total: heavy ≥ 64.5 mm, very heavy ≥ 115.6 mm, extremely heavy ≥ 204.5 mm." },
  { type: "high_wind", title: "High wind", text: "Blended daily max wind ≥ 39 km/h (Beaufort 6, strong breeze) or stronger." },
];

function ExtremesPage() {
  const [histLead, setHistLead] = useState(12);
  const cities = useCities();
  const navigate = useNavigate();
  const official = useApi("/live/official-alerts");
  const grid = useApi("/live/grid", { pollMs: 8000, poll: (g) => g.status !== "ready" });
  const boundary = useApi("/live/boundary");
  const hist = useApi("/extremes");
  const ready = (cities.data?.cities || []).filter((c) => c.status === "ready");
  const hazards = ready.flatMap((c) => c.summary.alerts.map((a) => ({ ...a, city: c })));
  const serious = hazards.filter((h) => h.level !== "notice")
    .sort((a, b) => (a.level === b.level ? (b.probability ?? 1) - (a.probability ?? 1) : a.level === "warning" ? -1 : 1));
  const unusual = hazards.filter((h) => h.level === "notice");
  const g = grid.data?.status === "ready" ? grid.data : null;

  return (
    <>
      <PageHeader eyebrow="LIVE · EXTREME WEATHER GUIDANCE" title="Heat waves, heavy rain & high wind"
        badge={<SourceBadge kind="live" detail={official.data ? `${official.data.alerts.length} official · ${serious.length} WEAVE` : "loading"} />} />
      <Page>
        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Warnings map" icon="crisis_alert"
              subtitle="Dashed circles: official warnings (NDMA SACHET). Red-ringed cities: WEAVE heat-wave, heavy-rain or high-wind signal in the next 3 days. Shading: blended rain today.">
              {!g ? <SkeletonCard lines={0} height={440} /> : (
                <IndiaGridMap grid={g} boundary={boundary.data} variable="precipitation_mm" day={0} layer="forecast"
                  cities={cities.data?.cities || []} official={official.data?.alerts || []} onCity={(c) => navigate(placeUrl(c.place))} />
              )}
            </DashboardCard>

            <DashboardCard title="Official warnings" icon="campaign" className="official-card"
              subtitle={official.data ? `${official.data.source} · updated ${ago(official.data.fetched_at)} · relayed verbatim` : "NDMA SACHET"}
              action={official.data && <span className="card-tag">{official.data.alerts.length} ACTIVE</span>}>
              {official.error ? <p className="muted">Official feed unavailable right now: {official.error.message}</p>
                : !official.data ? <SkeletonCard lines={4} height={0} />
                  : <OfficialAlerts alerts={official.data.alerts} limit={20} />}
            </DashboardCard>

            <DashboardCard title="How reliable are WEAVE’s ‘unusual day’ flags?" icon="fact_check"
              subtitle="Day-1 forecasts pooled over cities, on each city’s held-out 21-day window (complete IST days only)">
              {!cities.data ? <SkeletonCard lines={3} height={0} /> : (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead><tr><th>Variable</th><th>Cities</th><th>Days scored</th><th>Unusual days observed</th><th>Days flagged</th><th>Detected</th><th>False alarms</th><th>CSI</th></tr></thead>
                    <tbody>
                      {Object.entries(VARIABLES).map(([k, v]) => {
                        const p = pooled(ready, k);
                        return (
                          <tr key={k}>
                            <td>{v.label}</td><td>{p.cities}</td><td>{p.days}</td><td>{p.obs}</td><td>{p.fc}</td>
                            <td>{p.pod === null ? "no events" : pct(p.pod)}</td><td>{p.far === null ? "none flagged" : pct(p.far)}</td><td>{p.csi === null ? "—" : fmt(p.csi, 2)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <p className="card-caption">Unusual days (above the local 95th percentile for the date) are rare by construction, so three weeks per city gives small counts: treat this as a sanity check. The 2025 replay below covers a full year.</p>
                </div>
              )}
            </DashboardCard>

            <div className="section-label"><SourceBadge kind="historical" /></div>
            <div className="segmented" role="tablist" aria-label="Replay lead time">
              {[6, 12, 24].map((l) => (
                <button type="button" key={l} role="tab" aria-selected={l === histLead} className={l === histLead ? "is-active" : ""} onClick={() => setHistLead(l)}>{l} h</button>
              ))}
            </div>
            {hist.data ? <ExtremeVerification extremes={hist.data} lead={histLead} /> : hist.error ? <div className="chart-empty">{hist.error.message}</div> : <SkeletonCard lines={4} height={0} />}
          </div>

          <aside className="dashboard-grid__side">
            <DashboardCard title={`WEAVE signals (${serious.length})`} icon="warning" className="alert-card" subtitle="Today and the next 2 days, all tracked cities">
              {!cities.data ? <SkeletonCard lines={3} height={60} /> : serious.length === 0 ? (
                <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>No heat-wave, heavy-rain or high-wind signals right now.</div>
              ) : (
                <ul className="alert-list">
                  {serious.map((h) => (
                    <li key={h.city.label + h.type + h.date} className={"alert-item alert-item--" + (h.level === "warning" ? "high" : "moderate")}>
                      <button type="button" onClick={() => navigate(placeUrl(h.city.place))}>
                        <span className="alert-item__head">
                          <span className="alert-card__severity" style={{ color: LEVEL_STYLE[h.level].color }}>
                            <span className="material-symbols-outlined" aria-hidden="true">{HAZARD_ICON[h.type]}</span>{LEVEL_STYLE[h.level].label.toUpperCase()}
                          </span>
                          <span className="alert-card__probability">{h.day_label}</span>
                        </span>
                        <strong>{h.label} · {h.city.name}</strong>
                        <span className="alert-item__detail">{h.sentence}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {unusual.length > 0 && <p className="card-caption">Plus {unusual.length} “unusual for the date” notices (warmer, wetter or windier than the local 95th percentile) shown on each city’s page.</p>}
            </DashboardCard>

            <DashboardCard title="How WEAVE decides" icon="rule">
              <ul className="rule-list">
                {RULES.map((r) => (
                  <li key={r.type}><span className="material-symbols-outlined" aria-hidden="true">{HAZARD_ICON[r.type]}</span><div><strong>{r.title}</strong><p>{r.text}</p></div></li>
                ))}
              </ul>
              <p className="card-caption">
                <strong>Warning</strong> = the blend itself meets the rule. <strong>Watch</strong> = at least 30% of the 51 ECMWF ensemble members do.
                Official warnings always take precedence over WEAVE’s guidance.
              </p>
            </DashboardCard>
          </aside>
        </div>
      </Page>
    </>
  );
}

export default ExtremesPage;
