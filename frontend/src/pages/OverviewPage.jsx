import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import DashboardCard from "../components/DashboardCard";
import IndiaMap from "../components/IndiaMap";
import { AnimatedNumber, Bar, Page, Rise, SkeletonCard, Stagger } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import VariableTabs from "../components/VariableTabs";
import { LIVE_MODEL_BY_KEY, VARIABLES, ago, fmt, fmtDate, pct, placeUrl, severityOf } from "../format";
import { SUMMARY_LABELS, SUMMARY_UNITS, binScale, useCities } from "../live";

function OverviewPage() {
  const [variable, setVariable] = useState("precipitation_mm");
  const cities = useCities();
  const navigate = useNavigate();
  const d = cities.data;
  const ready = (d?.cities || []).filter((c) => c.status === "ready");
  const scale = binScale(ready.map((c) => c.summary.next_24h[variable]));
  const unit = SUMMARY_UNITS[variable];
  const digits = 1;

  const points = (d?.cities || []).filter((c) => c.place).map((c) => {
    const value = c.summary?.next_24h[variable];
    const alerts = c.summary?.alerts.filter((a) => a.target_variable === variable) || [];
    return {
      id: c.label, latitude: c.place.latitude, longitude: c.place.longitude,
      color: c.status === "ready" ? scale.color(value) : "#e2e8f0", radius: c.status === "ready" ? 9 : 5,
      ring: alerts.length ? "#d03b3b" : null,
      label: `${c.name}, ${c.state}`,
      detail: c.status === "ready" ? `${fmt(value, digits)} ${unit} · ${SUMMARY_LABELS[variable]}${alerts.length ? ` · extreme day ahead (${alerts.map((a) => fmtDate(a.date)).join(", ")})` : ""}` : c.status === "error" ? "Data unavailable" : "Computing…",
      onClick: c.status === "ready" ? () => navigate(placeUrl({ ...c.place })) : undefined,
    };
  });

  const alerts = ready
    .flatMap((c) => c.summary.alerts.map((a) => ({ ...a, city: c })))
    .sort((a, b) => (b.probability ?? 0) - (a.probability ?? 0) || a.date.localeCompare(b.date));

  const dataAge = ready.length ? ready.map((c) => c.summary.fetched_at).sort()[0] : null;

  return (
    <>
      <PageHeader eyebrow="LIVE / INDIA" title="Adaptive forecast blend"
        badge={<SourceBadge kind="live" detail={d ? `${d.ready}/${d.total} cities${dataAge ? " · fetched " + ago(dataAge) : ""}` : "connecting"} />} />
      <Page>
        {cities.error && <div className="banner banner--error" role="alert"><span className="material-symbols-outlined" aria-hidden="true">cloud_off</span><div><strong>Can’t reach the WEAVE API.</strong> {cities.error.message}</div></div>}

        <div className="page-intro">
          <div>
            <span className="eyebrow">ECMWF IFS · NCEP GFS · DWD ICON · ECMWF AIFS → ONE ADAPTIVE BLEND</span>
            <h2>{VARIABLES[variable].label} across India</h2>
          </div>
          <VariableTabs value={variable} onChange={setVariable} />
        </div>

        {d && d.ready < d.total && (
          <div className="progress-note" role="status">
            <Bar value={d.ready} max={d.total} color="#4a3aa7" />
            <span>Learning model skill for each city from its own verified forecast history: {d.ready} of {d.total} ready. Cities appear on the map as they finish.</span>
          </div>
        )}

        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Live map" icon="map" subtitle={`Colour = blended ${SUMMARY_LABELS[variable]} · red ring = extreme ${VARIABLES[variable].event.toLowerCase()} day today or in the next 2 days · click a city`}
              action={<span className="card-tag">{unit.toUpperCase()}</span>}>
              {!d ? <SkeletonCard lines={0} height={420} /> : (
                <IndiaMap points={points} ariaLabel={`Map of India coloured by ${SUMMARY_LABELS[variable]}`}
                  legend={scale.bins.length > 0 && (
                    <>
                      {scale.bins.map((b) => <span key={b.color}><i style={{ background: b.color }} />{fmt(b.from, digits)}–{fmt(b.to, digits)}</span>)}
                      <span><i className="ring" />extreme day ahead</span>
                    </>
                  )} />
              )}
            </DashboardCard>

            <DashboardCard title="All tracked cities" icon="table_rows" subtitle="Blended values and the member each city trusts most at lead day 1" className="city-table-card">
              {!d ? <SkeletonCard lines={6} height={0} /> : (
                <div className="table-scroll table-scroll--tall">
                  <table className="data-table city-table">
                    <thead>
                      <tr><th>City</th><th>Max temp °C</th><th>Rain mm</th><th>Max wind m/s</th><th>Most trusted ({VARIABLES[variable].label.toLowerCase()})</th><th /></tr>
                    </thead>
                    <tbody>
                      {d.cities.map((c) => {
                        const s = c.summary;
                        const dom = s?.dominant[variable]?.["1"];
                        return (
                          <tr key={c.label}>
                            <td>
                              {c.place && c.status === "ready" ? <Link to={placeUrl(c.place)}>{c.name}</Link> : c.name}
                              <small className="muted"> {c.state}</small>
                            </td>
                            {c.status === "ready" ? (
                              <>
                                <td>{fmt(s.next_24h.temperature_2m_c, 1)}</td>
                                <td>{fmt(s.next_24h.precipitation_mm, 1)}</td>
                                <td>{fmt(s.next_24h.wind_speed_10m, 1)}</td>
                                <td>{dom ? <span className="model-chip"><i style={{ background: LIVE_MODEL_BY_KEY[dom.model].color }} />{LIVE_MODEL_BY_KEY[dom.model].label} {pct(dom.weight)}</span> : "—"}</td>
                                <td>{s.alerts.length > 0 && <span className="material-symbols-outlined alert-dot" title="Extreme day in the next 3 days">warning</span>}</td>
                              </>
                            ) : (
                              <td colSpan={5} className="muted">{c.status === "error" ? `Unavailable: ${c.error}` : "Computing…"}</td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </DashboardCard>
          </div>

          <aside className="dashboard-grid__side">
            <DashboardCard title="Extreme days · next 3 days" icon="warning" className="alert-card"
              subtitle="Blended daily max temperature / rain total / max wind at or above that city’s 95th percentile for the date">
              {!d ? <SkeletonCard lines={3} height={60} /> : alerts.length === 0 ? (
                <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>No extreme days ahead in the {ready.length} cities computed so far.</div>
              ) : (
                <Stagger as="ul" className="alert-list">
                  {alerts.slice(0, 12).map((a) => {
                    const v = VARIABLES[a.target_variable];
                    const sev = severityOf(a.probability ?? 0);
                    const u = a.target_variable === "precipitation_mm" ? "mm" : v.unit;
                    return (
                      <Rise as="li" key={a.city.label + a.target_variable} className={"alert-item alert-item--" + sev}>
                        <button type="button" onClick={() => navigate(placeUrl(a.city.place))}>
                          <span className="alert-item__head">
                            <span className="alert-card__severity">{sev.toUpperCase()}</span>
                            <span className="alert-card__probability">{pct(a.probability)} of weighted models agree</span>
                          </span>
                          <strong>{v.event} · {a.city.name}</strong>
                          <span className="alert-item__detail">
                            {fmtDate(a.date)}{!a.complete && ` (from ${a.first_hour_ist} IST)`} · blend {fmt(a.value, 1)} {u} vs p95 {fmt(a.threshold, 1)} {u}
                          </span>
                        </button>
                      </Rise>
                    );
                  })}
                </Stagger>
              )}
            </DashboardCard>

            <DashboardCard title="How this works" icon="hub" subtitle="Every number here is computed, never estimated by hand">
              <ol className="workflow-stages">
                <li>Fetch the latest runs of 3 NWP models and 1 AI model</li>
                <li>Score each model’s archived forecasts against ERA5 at this city</li>
                <li>Pick and fit the best weighting on held-out days</li>
                <li>Blend, then flag days above the local 95th percentile for the date</li>
              </ol>
              <p className="card-caption"><Link to="/about">Method, data sources and limitations →</Link></p>
            </DashboardCard>

            {ready.length > 0 && (
              <DashboardCard title="Snapshot" icon="insights" subtitle={`Over ${ready.length} cities`}>
                <dl className="kv-list kv-list--big">
                  <div><dt>Wettest next 24 h</dt><dd>{(() => { const c = [...ready].sort((a, b) => b.summary.next_24h.precipitation_mm - a.summary.next_24h.precipitation_mm)[0]; return <>{c.name} · <AnimatedNumber value={c.summary.next_24h.precipitation_mm} digits={1} /> mm</>; })()}</dd></div>
                  <div><dt>Hottest next 24 h</dt><dd>{(() => { const c = [...ready].sort((a, b) => b.summary.next_24h.temperature_2m_c - a.summary.next_24h.temperature_2m_c)[0]; return <>{c.name} · <AnimatedNumber value={c.summary.next_24h.temperature_2m_c} digits={1} /> °C</>; })()}</dd></div>
                  <div><dt>Windiest next 24 h</dt><dd>{(() => { const c = [...ready].sort((a, b) => b.summary.next_24h.wind_speed_10m - a.summary.next_24h.wind_speed_10m)[0]; return <>{c.name} · <AnimatedNumber value={c.summary.next_24h.wind_speed_10m} digits={1} /> m/s</>; })()}</dd></div>
                </dl>
              </DashboardCard>
            )}
          </aside>
        </div>
      </Page>
    </>
  );
}

export default OverviewPage;
