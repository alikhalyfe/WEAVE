import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import DailyOutlook from "../components/DailyOutlook";
import DashboardCard from "../components/DashboardCard";
import ForecastCard from "../components/ForecastCard";
import IndiaMap from "../components/IndiaMap";
import LeadWeights from "../components/LeadWeights";
import { AnimatedNumber, Page, Rise, SkeletonCard, Stagger } from "../components/Motion";
import OfficialAlerts from "../components/OfficialAlerts";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import SearchBox from "../components/SearchBox";
import SkillByLead from "../components/SkillByLead";
import TimeSeriesChart from "../components/TimeSeriesChart";
import VariableTabs from "../components/VariableTabs";
import WeekOutlook from "../components/WeekOutlook";
import { BLEND, LIVE_MODELS, LIVE_VARIABLES, OBSERVED, REGIME_ICONS, ago, fmt, fmtIST, istHour, pct, placeUrl } from "../format";
import { placeFromSearch, useCities, useLiveForecast } from "../live";
import { readRecent, rememberPlace } from "../recent";

const dayTick = (iso) => (istHour(iso) === 0 ? fmtIST(iso, { weekday: true }).split(",")[0] : null);
const tip = (iso) => fmtIST(iso, { weekday: true }) + " IST";
const everyThirdDay = (iso) => {
  const label = istHour(iso) === 0 ? fmtIST(iso).split(",")[0] : null;
  return label && Number(label.split(" ")[0]) % 3 === 0 ? label : null;
};
const scaled = (x, k) => (x === null || x === undefined ? null : x * k);

function PlacePicker() {
  const cities = useCities();
  const ready = (cities.data?.cities || []).filter((c) => c.status === "ready");
  return (
    <Page>
      <div className="picker">
        <img src="/logo-192.png" alt="" className="picker__logo" width="72" height="72" />
        <h2>Which place in India?</h2>
        <p className="muted">Search any city, town or village. The first forecast for a new place takes 10–20 seconds while WEAVE checks how each of the 5 models has performed there.</p>
        <SearchBox autoFocus />
        {ready.length > 0 && (
          <Stagger className="chip-row">
            {ready.map((c) => <Rise key={c.label}><Link className="chip" to={placeUrl(c.place)}>{c.name}</Link></Rise>)}
          </Stagger>
        )}
      </div>
    </Page>
  );
}

function next24(points, variable) {
  const next = points.filter((p) => p.hours_ahead < 24 && p.blended !== null).map((p) => p.blended);
  if (!next.length) return null;
  return variable === "precipitation_mm" ? next.reduce((a, b) => a + b, 0) : Math.max(...next);
}

function ForecastPage() {
  const location = useLocation();
  const fromUrl = placeFromSearch(location.search);
  const place = fromUrl || readRecent()[0] || null;
  const [variable, setVariable] = useState("precipitation_mm");
  const fc = useLiveForecast(place);
  const d = fc.data;

  const urlKey = fromUrl ? JSON.stringify(fromUrl) : null;
  useEffect(() => {
    if (urlKey) rememberPlace(JSON.parse(urlKey));
  }, [urlKey]);

  const v = LIVE_VARIABLES[variable];
  const k = v.scale;
  const vd = d?.variables[variable];
  const series = useMemo(() => [
    ...LIVE_MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color, faint: true, value: (p) => scaled(p.members[m.key], k) })),
    { key: "blended", label: BLEND.label, color: BLEND.color, width: 3, value: (p) => scaled(p.blended, k) },
  ], [k]);
  const recentSeries = useMemo(() => [
    ...LIVE_MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color, faint: true, value: (p) => scaled(p[m.key], k) })),
    { key: "blended", label: BLEND.label, color: BLEND.color, width: 2.6, value: (p) => scaled(p.blended, k) },
    { key: "actual", label: OBSERVED.label, color: OBSERVED.color, dash: "5 4", value: (p) => scaled(p.actual, k) },
  ], [k]);

  if (!place) {
    return (
      <>
        <PageHeader eyebrow="LIVE / FORECAST" title="Forecast" search={false} badge={<SourceBadge kind="live" />} />
        <PlacePicker />
      </>
    );
  }

  const firstFull = vd?.days.find((x) => x.complete);
  // Daily-max thresholds are comparable to hourly temperature / wind; rain's is a daily total, so no line.
  const threshold = variable !== "precipitation_mm" ? scaled(firstFull?.threshold, k) : null;
  const regimes = vd ? vd.points.filter((p) => p.hours_ahead < 72).reduce((acc, p) => ({ ...acc, [p.regime]: (acc[p.regime] || 0) + 1 }), {}) : {};
  const days = vd?.days.map((x) => ({ ...x, blended: scaled(x.blended, k), threshold: scaled(x.threshold, k) }));
  const skill = vd?.skill.map((s) => ({ ...s, mae: scaled(s.mae, k) }));
  const nearOfficial = d?.official_alerts;
  const runs = d ? Object.values(d.model_runs).filter((r) => r.initialised).length : 0;

  return (
    <>
      <PageHeader eyebrow={`LIVE / ${place.state ? place.state.toUpperCase() + " / " : ""}${place.name.toUpperCase()}`} title={place.name}
        badge={<SourceBadge kind="live" detail={d ? `updated ${ago(d.fetched_at)}` : fc.error ? "unavailable" : "loading"} />} />
      <Page>
        {fc.error && <div className="banner banner--error" role="alert"><span className="material-symbols-outlined" aria-hidden="true">cloud_off</span><div><strong>Live data unavailable.</strong> {fc.error.message}</div></div>}
        {!d && !fc.error && (
          <>
            <div className="progress-note" role="status">
              <span className="material-symbols-outlined spin" aria-hidden="true">progress_activity</span>
              <span>Learning how each model performs in {place.name}: 120 days of archived ECMWF, GFS, ICON, ensemble and AIFS forecasts checked against ERA5. The first load takes 10–20 s, then it’s cached.</span>
            </div>
            <SkeletonCard lines={6} height={0} />
            <div className="forecast-grid">{[0, 1, 2, 3].map((i) => <SkeletonCard key={i} lines={2} height={30} />)}</div>
          </>
        )}

        {d && (
          <>
            <div className="dashboard-grid">
              <div className="dashboard-grid__main">
                <DashboardCard title="The week ahead" icon="event_note" className="week-card"
                  subtitle={`Issued ${fmtIST(d.issued_at)} IST · blended from ${LIVE_MODELS.length} models · tap a day for details`}>
                  <WeekOutlook outlook={d.outlook} place={place.name} />
                </DashboardCard>
              </div>
              <aside className="dashboard-grid__side">
                <DashboardCard title="Official warnings nearby" icon="campaign" className="official-card"
                  subtitle={`NDMA SACHET (IMD, CWC, state authorities) · within 150 km${place.state ? ` or naming ${place.state}` : ""}`}>
                  {nearOfficial?.error ? <p className="muted">{nearOfficial.error}</p>
                    : <OfficialAlerts alerts={nearOfficial?.alerts} limit={4} showDistance empty={`No active official warnings near ${place.name}.`} />}
                </DashboardCard>
                <DashboardCard title="Location" icon="location_on" subtitle={`${place.state || "India"} · ${place.latitude.toFixed(2)}°N ${place.longitude.toFixed(2)}°E${d.elevation_m != null ? ` · ${Math.round(d.elevation_m)} m` : ""}`}>
                  <IndiaMap height={180} focus={place} points={[{ id: "here", latitude: place.latitude, longitude: place.longitude, color: BLEND.color, radius: 9, label: place.name }]} ariaLabel={`Map around ${place.name}`} />
                </DashboardCard>
              </aside>
            </div>

            <div className="page-intro page-intro--section">
              <div>
                <span className="eyebrow">THE NUMBERS BEHIND IT</span>
                <h2>Adaptive blend in detail</h2>
              </div>
              <VariableTabs value={variable} onChange={setVariable} />
            </div>

            <Stagger className="forecast-grid" as="section">
              {Object.entries(LIVE_VARIABLES).map(([key, meta]) => (
                <Rise key={key}>
                  <ForecastCard label={meta.label} icon={meta.icon} accent={meta.accent} active={key === variable} onClick={() => setVariable(key)}
                    value={<AnimatedNumber value={scaled(next24(d.variables[key].points, key), meta.scale)} digits={meta.digits} />} unit={meta.unit}
                    detail={key === "precipitation_mm" ? "Blended total, next 24 h" : "Blended max, next 24 h"} />
                </Rise>
              ))}
              <Rise>
                <ForecastCard label="Weather regime" icon={REGIME_ICONS[vd.points[0]?.regime] || "cloud"} accent="indigo"
                  value={vd.points[0]?.regime || "—"} unit="" detail={`Next 72 h: ${Object.entries(regimes).map(([r, n]) => `${r} ${n} h`).join(" · ")}`} />
              </Rise>
            </Stagger>

            <div className="dashboard-grid">
              <div className="dashboard-grid__main">
                <DashboardCard title={`${v.label} · next 7 days`} icon="show_chart" className="forecast-comparison"
                  subtitle={`Hourly ${v.hourlyUnit}, IST. Thin lines: the 5 models. Thick: WEAVE adaptive blend.`}
                  action={<span className="card-tag">LIVE · {runs}/{LIVE_MODELS.length} RUNS</span>}>
                  <TimeSeriesChart points={vd.points} series={series} time={(p) => p.time} fmtX={dayTick} fmtTip={tip}
                    digits={v.digits} zero={variable !== "temperature_2m_c"} label={`${v.label} forecast for ${place.name}`}
                    threshold={threshold != null ? { value: threshold, label: `unusual above ${fmt(threshold, v.digits)} ${v.unit}` } : null}
                    tipExtra={(p) => `+${p.hours_ahead} h · day ${p.lead_day} · regime ${p.regime}`} />
                  <h3 className="subhead">Day by day <small className="muted">IST days · with the 51-member ensemble’s spread</small></h3>
                  <DailyOutlook days={days} variable={variable} digits={v.digits} />
                </DashboardCard>

                <DashboardCard title="How much each model counts" icon="tune" subtitle={`Blend weights per day ahead, learned from ${place.name}’s verified history (season, weather regime, hour of day)`}
                  action={<span className="card-tag">{d.history_window_days}-DAY HISTORY</span>}>
                  <LeadWeights points={vd.points} chosen={vd.chosen} />
                </DashboardCard>

                <DashboardCard title="Recent track record" icon="fact_check"
                  subtitle={`Day-1 forecasts vs ERA5 observations, ${fmtIST(d.evaluation_window[0]).split(",")[0]} – ${fmtIST(d.evaluation_window[1]).split(",")[0]} (held out: never used to fit or choose weights)`}>
                  {vd.recent_verification.length ? (
                    <TimeSeriesChart points={vd.recent_verification} time={(p) => p.time} fmtX={everyThirdDay}
                      fmtTip={tip} digits={v.digits} zero={variable !== "temperature_2m_c"} height={200} label="Day-1 forecasts versus observations" series={recentSeries} />
                  ) : <div className="chart-empty">No verified day-1 history for this place yet.</div>}
                </DashboardCard>

                <DashboardCard title="Accuracy by days ahead" icon="analytics" subtitle={`Mean absolute error (${v.unit}) on the held-out window · lower is better`}>
                  <SkillByLead skill={skill} digits={v.digits > 1 ? 2 : 1} unit={v.unit} />
                </DashboardCard>
              </div>

              <aside className="dashboard-grid__side">
                <DashboardCard title="Unusual days" icon="insights" className="alert-card"
                  subtitle={`${v.label}: blended daily ${variable === "precipitation_mm" ? "total" : "max"} above the 95th percentile for the date (ERA5, last 2 years, ±15 days)`}>
                  {days.filter((x) => x.event).length === 0 ? (
                    <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>Nothing unusual for the time of year.</div>
                  ) : (
                    <ul className="alert-list">
                      {days.filter((x) => x.event).map((x) => (
                        <li key={x.date} className="alert-item alert-item--low">
                          <div className="alert-item__static">
                            <span className="alert-item__head"><span className="alert-card__severity">UNUSUAL</span><span className="alert-card__probability">{pct(x.probability)} of weighted models agree</span></span>
                            <strong>{new Date(x.date + "T00:00:00Z").toUTCString().slice(0, 11)}</strong>
                            <span className="alert-item__detail">Blend {fmt(x.blended, v.digits)} vs p95 {fmt(x.threshold, v.digits)} {v.unit}{!x.complete && ` · from ${x.first_hour_ist} IST`}</span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                  {vd.event_verification.find((e) => e.lead_day === 1) && (() => {
                    const e = vd.event_verification.find((x) => x.lead_day === 1);
                    return (
                      <p className="card-caption">
                        Held-out check (day-1, {e.days} days): {e.observed_events} unusual day{e.observed_events === 1 ? "" : "s"} observed, {e.forecast_events} flagged
                        {e.pod !== null && ` · detected ${pct(e.pod)}`}{e.far !== null && ` · false alarms ${pct(e.far)}`}.
                      </p>
                    );
                  })()}
                </DashboardCard>

                <DashboardCard title="Model runs" icon="schedule" subtitle="Latest run of each member (UTC)">
                  <dl className="kv-list">
                    {LIVE_MODELS.map((m) => (
                      <div key={m.key}>
                        <dt><i className="swatch" style={{ background: m.color }} />{m.label} · {m.kind}</dt>
                        <dd>{d.model_runs[m.key]?.initialised ? d.model_runs[m.key].initialised.slice(5, 16).replace("T", " ") : "unknown"}</dd>
                      </div>
                    ))}
                    <div><dt>Ensemble members</dt><dd>{d.ensemble_members ?? "unavailable"}</dd></div>
                    <div><dt>ERA5 truth until</dt><dd>{fmtIST(d.truth_available_until)} IST</dd></div>
                    <div><dt>Skill last learned</dt><dd>{ago(d.skill_computed_at)}</dd></div>
                  </dl>
                </DashboardCard>
              </aside>
            </div>
          </>
        )}
      </Page>
    </>
  );
}

export default ForecastPage;
