import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import DailyOutlook from "../components/DailyOutlook";
import DashboardCard from "../components/DashboardCard";
import ForecastCard from "../components/ForecastCard";
import IndiaMap from "../components/IndiaMap";
import LeadWeights from "../components/LeadWeights";
import { AnimatedNumber, Page, Rise, SkeletonCard, Stagger } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import SearchBox from "../components/SearchBox";
import SkillByLead from "../components/SkillByLead";
import TimeSeriesChart from "../components/TimeSeriesChart";
import VariableTabs from "../components/VariableTabs";
import { BLEND, LIVE_MODELS, OBSERVED, REGIME_ICONS, VARIABLES, ago, fmt, fmtDate, fmtIST, istHour, pct, placeUrl, severityOf } from "../format";
import { placeFromSearch, useCities, useLiveForecast } from "../live";
import { readRecent, rememberPlace } from "../recent";

const memberSeries = LIVE_MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color, faint: true, value: (p) => p.members[m.key] }));
const blendSeries = { key: "blended", label: BLEND.label, color: BLEND.color, width: 3, value: (p) => p.blended };
const dayTick = (iso) => (istHour(iso) === 0 ? fmtIST(iso, { weekday: true }).split(",")[0] : null);
const tip = (iso) => fmtIST(iso, { weekday: true }) + " IST";
const everyThirdDay = (iso) => {
  const label = istHour(iso) === 0 ? fmtIST(iso).split(",")[0] : null;
  return label && Number(label.split(" ")[0]) % 3 === 0 ? label : null;
};

function PlacePicker() {
  const cities = useCities();
  const ready = (cities.data?.cities || []).filter((c) => c.status === "ready");
  return (
    <Page>
      <div className="picker">
        <span className="material-symbols-outlined picker__icon" aria-hidden="true">travel_explore</span>
        <h2>Pick a place in India</h2>
        <p className="muted">Search any city or town. The first forecast for a new place takes a few seconds while WEAVE learns how each model performs there.</p>
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

function summary(points, variable) {
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

  if (!place) {
    return (
      <>
        <PageHeader eyebrow="LIVE / FORECAST" title="Forecast" search={false} badge={<SourceBadge kind="live" />} />
        <PlacePicker />
      </>
    );
  }

  const v = VARIABLES[variable];
  const vd = d?.variables[variable];
  const events = vd ? vd.days.filter((x) => x.event) : [];
  const firstFull = vd?.days.find((x) => x.complete);
  // Daily-max thresholds are comparable to hourly temperature / wind; rain's is a daily total, so no line.
  const threshold = variable !== "precipitation_mm" ? firstFull?.threshold : null;
  const regimes = vd ? vd.points.filter((p) => p.hours_ahead < 72).reduce((acc, p) => ({ ...acc, [p.regime]: (acc[p.regime] || 0) + 1 }), {}) : {};

  return (
    <>
      <PageHeader eyebrow={`LIVE / ${place.state ? place.state.toUpperCase() + " / " : ""}${place.name.toUpperCase()}`} title={place.name}
        badge={<SourceBadge kind="live" detail={d ? `fetched ${ago(d.fetched_at)}` : fc.error ? "unavailable" : "loading"} />} />
      <Page>
        {fc.error && <div className="banner banner--error" role="alert"><span className="material-symbols-outlined" aria-hidden="true">cloud_off</span><div><strong>Live data unavailable.</strong> {fc.error.message}</div></div>}
        {!d && !fc.error && (
          <>
            <div className="progress-note" role="status">
              <span className="material-symbols-outlined spin" aria-hidden="true">progress_activity</span>
              <span>Learning model skill for {place.name}: 120 days of archived ECMWF, GFS, ICON and AIFS forecasts checked against ERA5. First load takes 10–20 s, then it’s cached.</span>
            </div>
            <div className="forecast-grid">{[0, 1, 2, 3].map((i) => <SkeletonCard key={i} lines={2} height={30} />)}</div>
            <SkeletonCard lines={1} height={260} />
          </>
        )}

        {d && (
          <>
            <div className="page-intro">
              <div>
                <span className="eyebrow">ISSUED {fmtIST(d.issued_at).toUpperCase()} IST · NEXT 7 DAYS · {place.latitude.toFixed(2)}°N {place.longitude.toFixed(2)}°E</span>
                <h2>Adaptive blend of 4 models</h2>
              </div>
              <VariableTabs value={variable} onChange={setVariable} />
            </div>

            <Stagger className="forecast-grid" as="section">
              {Object.entries(VARIABLES).map(([key, meta]) => {
                const value = summary(d.variables[key].points, key);
                const hasAlert = d.variables[key].days.slice(0, 3).some((x) => x.event);
                return (
                  <Rise key={key}>
                    <ForecastCard label={meta.label} icon={meta.icon} accent={meta.accent} active={key === variable} onClick={() => setVariable(key)}
                      value={<AnimatedNumber value={value} digits={1} />} unit={key === "precipitation_mm" ? "mm" : meta.unit}
                      detail={key === "precipitation_mm" ? "Blended total, next 24 h" : `Blended max, next 24 h`}
                      alert={hasAlert ? `${meta.event} day ahead` : null} />
                  </Rise>
                );
              })}
              <Rise>
                <ForecastCard label="Forecast regime" icon={REGIME_ICONS[vd.points[0]?.regime] || "cloud"} accent="indigo"
                  value={vd.points[0]?.regime || "—"} unit="" detail={`Next 72 h: ${Object.entries(regimes).map(([r, n]) => `${r} ${n} h`).join(" · ")}`} />
              </Rise>
            </Stagger>

            <div className="dashboard-grid">
              <div className="dashboard-grid__main">
                <DashboardCard title={`${v.label} · next 7 days`} icon="show_chart" className="forecast-comparison"
                  subtitle={`Hourly ${v.unit}, IST. Thin lines: individual models. Thick: WEAVE adaptive blend.`}
                  action={<span className="card-tag">LIVE · {Object.values(d.model_runs).filter((r) => r.initialised).length}/4 RUNS</span>}>
                  <TimeSeriesChart points={vd.points} series={[...memberSeries, blendSeries]} time={(p) => p.time} fmtX={dayTick} fmtTip={tip}
                    digits={v.digits} zero={variable !== "temperature_2m_c"} label={`${v.label} forecast for ${place.name}`}
                    threshold={threshold != null ? { value: threshold, label: `daily-max p95 ${fmt(threshold, v.digits)} ${v.unit}` } : null}
                    tipExtra={(p) => `+${p.hours_ahead} h · lead day ${p.lead_day} · regime ${p.regime}`} />
                  <h3 className="subhead">Daily outlook <small className="muted">IST days · extreme if the blended daily {variable === "precipitation_mm" ? "total" : "maximum"} reaches the 95th percentile for this time of year</small></h3>
                  <DailyOutlook days={vd.days} variable={variable} digits={v.digits > 1 ? 1 : v.digits} />
                </DashboardCard>

                <DashboardCard title="How much each model counts" icon="tune" subtitle="Mean blend weight per lead day, learned from this place’s verified history"
                  action={<span className="card-tag">{d.history_window_days}-DAY HISTORY</span>}>
                  <LeadWeights points={vd.points} chosen={vd.chosen} />
                </DashboardCard>

                <DashboardCard title="Recent track record" icon="fact_check"
                  subtitle={`Day-1 forecasts vs ERA5 observations, ${fmtIST(d.evaluation_window[0], { date: true }).split(",")[0]} – ${fmtIST(d.evaluation_window[1]).split(",")[0]} (held out: not used to fit or choose weights)`}>
                  {vd.recent_verification.length ? (
                    <TimeSeriesChart points={vd.recent_verification} time={(p) => p.time} fmtX={everyThirdDay}
                      fmtTip={tip} digits={v.digits} zero={variable !== "temperature_2m_c"} height={200} label="Day-1 forecasts versus observations"
                      series={[
                        ...LIVE_MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color, faint: true, value: (p) => p[m.key] })),
                        { key: "blended", label: BLEND.label, color: BLEND.color, width: 2.6, value: (p) => p.blended },
                        { key: "actual", label: OBSERVED.label, color: OBSERVED.color, dash: "5 4", value: (p) => p.actual },
                      ]} />
                  ) : <div className="chart-empty">No verified day-1 history for this place yet.</div>}
                </DashboardCard>

                <DashboardCard title="Skill by lead time" icon="analytics" subtitle={`Mean absolute error (${v.unit}) on the held-out window · lower is better`}>
                  <SkillByLead skill={vd.skill} digits={v.digits > 1 ? 2 : 1} unit={v.unit} />
                </DashboardCard>
              </div>

              <aside className="dashboard-grid__side">
                <DashboardCard title="Location" icon="location_on" subtitle={place.state || "India"}>
                  <IndiaMap height={220} focus={place} points={[{ id: "here", latitude: place.latitude, longitude: place.longitude, color: BLEND.color, radius: 9, label: place.name }]} ariaLabel={`Map around ${place.name}`} />
                </DashboardCard>

                <DashboardCard title="Extreme days" icon="warning" className="alert-card"
                  subtitle={`${v.event}: blended daily ${variable === "precipitation_mm" ? "total" : "max"} ≥ 95th percentile for the date (last 2 years of ERA5, ±15 days)`}>
                  {events.length === 0 ? (
                    <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>No {v.event.toLowerCase()} days in the forecast.</div>
                  ) : (
                    <ul className="alert-list">
                      {events.map((x) => {
                        const sev = severityOf(x.probability ?? 0);
                        return (
                          <li key={x.date} className={"alert-item alert-item--" + sev}>
                            <div className="alert-item__static">
                              <span className="alert-item__head"><span className="alert-card__severity">{sev.toUpperCase()}</span><span className="alert-card__probability">{pct(x.probability)} weighted agreement</span></span>
                              <strong>{fmtDate(x.date)}</strong>
                              <span className="alert-item__detail">Blend {fmt(x.blended, v.digits)} vs p95 {fmt(x.threshold, v.digits)} {variable === "precipitation_mm" ? "mm" : v.unit}{!x.complete && ` · partial day from ${x.first_hour_ist} IST`}</span>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  {vd.event_verification.find((e) => e.lead_day === 1) && (() => {
                    const e = vd.event_verification.find((x) => x.lead_day === 1);
                    return (
                      <p className="card-caption">
                        Held-out check, day-1 forecasts over {e.days} days: {e.observed_events} extreme day{e.observed_events === 1 ? "" : "s"} observed, {e.forecast_events} flagged
                        {e.pod !== null && ` · detected ${pct(e.pod)}`}{e.far !== null && ` · false alarms ${pct(e.far)}`}.
                      </p>
                    );
                  })()}
                </DashboardCard>

                <DashboardCard title="Model runs" icon="schedule" subtitle="Latest initialisation of each member (UTC)">
                  <dl className="kv-list">
                    {LIVE_MODELS.map((m) => (
                      <div key={m.key}>
                        <dt><i className="swatch" style={{ background: m.color }} />{m.label} · {m.kind}</dt>
                        <dd>{d.model_runs[m.key]?.initialised ? d.model_runs[m.key].initialised.slice(5, 16).replace("T", " ") : "unknown"}</dd>
                      </div>
                    ))}
                    <div><dt>ERA5 truth available until</dt><dd>{fmtIST(d.truth_available_until)} IST</dd></div>
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
