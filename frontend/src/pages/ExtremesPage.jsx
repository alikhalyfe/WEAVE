import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import ExtremeVerification from "../components/ExtremeVerification";
import IndiaMap from "../components/IndiaMap";
import { Page, Rise, SkeletonCard, Stagger } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import { VARIABLES, fmt, fmtDate, pct, placeUrl, severityOf } from "../format";
import { useCities } from "../live";

const SEVERITY = { high: "#d03b3b", moderate: "#ec835a", low: "#fab219" };

/** Pool per-city day-1 verification into one contingency table. */
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
  return {
    cities, days, obs, fc, hits,
    pod: obs ? hits / obs : null,
    far: fc ? (fc - hits) / fc : null,
    csi: obs + fc - hits ? hits / (obs + fc - hits) : null,
  };
}

function ExtremesPage() {
  const [histLead, setHistLead] = useState(12);
  const cities = useCities();
  const navigate = useNavigate();
  const ready = (cities.data?.cities || []).filter((c) => c.status === "ready");
  const alerts = ready.flatMap((c) => c.summary.alerts.map((a) => ({ ...a, city: c })))
    .sort((a, b) => (b.probability ?? 0) - (a.probability ?? 0) || a.date.localeCompare(b.date));
  const hist = useApi("/extremes");

  const points = ready.map((c) => {
    const top = c.summary.alerts.reduce((m, a) => (!m || (a.probability ?? 0) > (m.probability ?? 0) ? a : m), null);
    return {
      id: c.label, latitude: c.place.latitude, longitude: c.place.longitude,
      color: top ? SEVERITY[severityOf(top.probability ?? 0)] : "#cbd5e1", radius: top ? 10 : 5,
      label: c.name,
      detail: top ? c.summary.alerts.map((a) => `${VARIABLES[a.target_variable].event} ${fmtDate(a.date)} (${pct(a.probability)})`).join(" · ") : "No extreme day in the next 3 days",
      onClick: () => navigate(placeUrl(c.place)),
    };
  });

  return (
    <>
      <PageHeader eyebrow="LIVE / EXTREME WEATHER GUIDANCE" title="Heavy rain, heat & high wind"
        badge={<SourceBadge kind="live" detail={`${ready.length} cities · next 3 days`} />} />
      <Page>
        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Where extremes are signalled" icon="crisis_alert"
              subtitle="A day is extreme when the blended daily max temperature, rain total or max wind reaches that city’s 95th percentile for the date (last 2 years of ERA5, ±15 days). Colour = share of weighted models that agree.">
              {!cities.data ? <SkeletonCard lines={0} height={420} /> : (
                <IndiaMap points={points} ariaLabel="Map of extreme weather signals"
                  legend={<>
                    {Object.entries(SEVERITY).map(([k, c]) => <span key={k}><i style={{ background: c }} />{k} agreement</span>)}
                    <span><i style={{ background: "#cbd5e1" }} />no signal</span>
                  </>} />
              )}
            </DashboardCard>

            <DashboardCard title="Live guidance: how reliable has it been?" icon="fact_check"
              subtitle="Day-1 forecasts, pooled over cities, on each city’s held-out 21-day window (complete IST days only)">
              {!cities.data ? <SkeletonCard lines={3} height={0} /> : (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead><tr><th>Event</th><th>Cities</th><th>Days scored</th><th>Extreme days observed</th><th>Days flagged</th><th>Detected (POD)</th><th>False alarms (FAR)</th><th>CSI</th></tr></thead>
                    <tbody>
                      {Object.entries(VARIABLES).map(([k, v]) => {
                        const p = pooled(ready, k);
                        return (
                          <tr key={k}>
                            <td>{v.event}</td><td>{p.cities}</td><td>{p.days}</td><td>{p.obs}</td><td>{p.fc}</td>
                            <td>{p.pod === null ? "no events" : pct(p.pod)}</td>
                            <td>{p.far === null ? "none flagged" : pct(p.far)}</td>
                            <td>{p.csi === null ? "—" : fmt(p.csi, 2)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <p className="card-caption">Extreme days are rare by construction (about 1 in 20), so three weeks per city gives small counts. Treat this as a sanity check, not a skill claim. The 2025 replay below has a full year.</p>
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
            <DashboardCard title={`Extreme days ahead (${alerts.length})`} icon="warning" className="alert-card" subtitle="Today and the next 2 IST days, all computed cities">
              {!cities.data ? <SkeletonCard lines={3} height={60} /> : alerts.length === 0 ? (
                <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>No extreme days ahead right now.</div>
              ) : (
                <Stagger as="ul" className="alert-list">
                  {alerts.map((a) => {
                    const v = VARIABLES[a.target_variable];
                    const sev = severityOf(a.probability ?? 0);
                    const u = a.target_variable === "precipitation_mm" ? "mm" : v.unit;
                    return (
                      <Rise as="li" key={a.city.label + a.target_variable} className={"alert-item alert-item--" + sev}>
                        <button type="button" onClick={() => navigate(placeUrl(a.city.place))}>
                          <span className="alert-item__head"><span className="alert-card__severity">{sev.toUpperCase()}</span><span className="alert-card__probability">{pct(a.probability)} agree</span></span>
                          <strong>{v.event} · {a.city.name}</strong>
                          <span className="alert-item__detail">{fmtDate(a.date)}{!a.complete && ` (from ${a.first_hour_ist} IST)`} · blend {fmt(a.value, 1)} {u} vs p95 {fmt(a.threshold, 1)} {u}</span>
                        </button>
                      </Rise>
                    );
                  })}
                </Stagger>
              )}
            </DashboardCard>
          </aside>
        </div>
      </Page>
    </>
  );
}

export default ExtremesPage;
