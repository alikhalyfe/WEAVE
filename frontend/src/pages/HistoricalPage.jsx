import { useEffect, useState } from "react";
import { qs, useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import ExtremeVerification from "../components/ExtremeVerification";
import ExtremeWeatherAlert from "../components/ExtremeWeatherAlert";
import ForecastCard from "../components/ForecastCard";
import ForecastChart from "../components/ForecastChart";
import Header from "../components/Header";
import LiveBlend from "../components/LiveBlend";
import ModelWeights from "../components/ModelWeights";
import PerformanceCard from "../components/PerformanceCard";
import { Page } from "../components/Motion";
import WeatherRegime from "../components/WeatherRegime";
import WeightMap from "../components/WeightMap";
import WorkflowCard from "../components/WorkflowCard";
import YearTimeline from "../components/YearTimeline";
import { REGIME_ICONS, VARIABLES, addHours, fmt, fmtTime } from "../format";

// Selection lives in the URL so any view can be shared as a link.
function readUrl() {
  const p = new URLSearchParams(window.location.search);
  return {
    location: p.get("location") || null,
    variable: VARIABLES[p.get("variable")] ? p.get("variable") : "precipitation_mm",
    lead: Number(p.get("lead")) || 12,
    time: p.get("time") || null,
  };
}

/** The 2025 research replay: 3 ML members at 5 Maharashtra ERA5 points. */
function HistoricalPage() {
  const [sel, setSel] = useState(readUrl);
  const meta = useApi("/meta");
  const m = meta.data;

  // Until the user picks, fall back to the defaults the workflow published.
  const location = sel.location || m?.default_view?.location || m?.locations[0]?.location;
  const time = sel.time || (m ? (m.default_view?.issue_time || m.evaluation_period[1]).replace(" ", "T").slice(0, 19) : null);
  const { variable, lead } = sel;
  const ready = Boolean(m && location && time);

  useEffect(() => {
    if (ready) window.history.replaceState(window.history.state, "", "/historical" + qs({ location, variable, lead, time }));
  }, [ready, location, variable, lead, time]);

  const snapshot = useApi(ready ? "/snapshot" + qs({ time, lead }) : null);
  const series = useApi(ready ? "/series" + qs({ location, variable, lead, time }) : null);
  const skill = useApi(ready ? "/skill" + qs({ variable, lead }) : null);
  const weights = useApi(ready ? "/weights" + qs({ variable }) : null);
  const extremes = useApi(ready ? "/extremes" : null);
  const daily = useApi(ready ? "/daily" + qs({ location, variable, lead }) : null);

  const update = (patch) => setSel((s) => ({ ...s, location, time, ...patch }));
  const status = meta.error ? "offline" : m ? "online" : "loading";
  const vmeta = VARIABLES[variable];
  const rows = snapshot.data?.rows || [];
  const here = (v) => rows.find((r) => r.location === location && r.target_variable === v);
  const current = here(variable);
  const varRows = rows.filter((r) => r.target_variable === variable);
  const validTime = snapshot.data?.valid_time;

  return (
    <>
        <Header meta={m} location={location} variable={variable} lead={lead} time={time} onChange={update} status={status} />
        <Page>
          <div className="banner banner--info">
            <span className="material-symbols-outlined" aria-hidden="true">history</span>
            <div><strong>Historical replay, not live.</strong> A research experiment: Persistence, Random Forest and gradient-boosting members
              trained on 2021–2024 ERA5 and verified on every hour of 2025 at 5 Maharashtra sites. For today’s forecasts use the Live pages.</div>
          </div>
          {meta.error && (
            <div className="banner banner--error" role="alert">
              <span className="material-symbols-outlined" aria-hidden="true">cloud_off</span>
              <div>
                <strong>Can’t reach the WEAVE API.</strong> Start it from the repo root with{" "}
                <code>uvicorn src.api.main:app</code> (after <code>python -m src.workflow</code> has produced the artifacts).
                <br /><small>{meta.error.message}</small>
              </div>
            </div>
          )}

          {ready && (
            <>
              <div className="page-intro">
                <div>
                  <span className="eyebrow">{location?.toUpperCase()} / ISSUED {fmtTime(time, true).toUpperCase()} UTC / +{lead}H</span>
                  <h2>Adaptive forecast blend</h2>
                </div>
                <div className="time-stepper" role="group" aria-label="Step issue time">
                  {[[-24, "−1d"], [-6, "−6h"], [6, "+6h"], [24, "+1d"]].map(([h, label]) => (
                    <button type="button" key={label} onClick={() => update({ time: addHours(time, h) })}>{label}</button>
                  ))}
                </div>
              </div>

              <section className="forecast-grid" aria-label="Blended forecast summary">
                {Object.entries(VARIABLES).map(([key, v]) => {
                  const r = here(key);
                  return (
                    <ForecastCard key={key} label={v.label} value={fmt(r?.blended, v.digits)} unit={v.unit} icon={v.icon} accent={v.accent}
                      active={key === variable} onClick={() => update({ variable: key })}
                      detail={r ? `Observed ${fmt(r.actual_value, v.digits)} · valid ${fmtTime(validTime)}` : "—"}
                      alert={r?.guidance_event ? `${v.event} guidance` : null} />
                  );
                })}
                <ForecastCard label="Weather Regime" value={current?.weather_regime || "—"} unit="" icon={REGIME_ICONS[current?.weather_regime] || "cloud"}
                  accent="indigo" detail={current ? `${current.season} · at issue time` : "—"} />
              </section>

              <div className="dashboard-grid">
                <div className="dashboard-grid__main">
                  <DashboardCard id="forecast" title="Forecast Comparison" icon="show_chart"
                    subtitle={`${vmeta.label} (${vmeta.unit}) at ${location} by valid time — every point is a ${lead}h-ahead forecast`}
                    className="forecast-comparison" action={<span className="card-tag">{lead} HOUR LEAD</span>}>
                    {series.error ? <div className="chart-empty">{series.error.message}</div> : (
                      <ForecastChart points={series.data?.points} issueTime={time} variable={variable} meta={vmeta} lead={lead} />
                    )}
                    <YearTimeline daily={daily.data} issueTime={time} meta={vmeta}
                      onPick={(day) => update({ time: `${day}T${time.slice(11, 19)}` })} />
                  </DashboardCard>

                  <div className="dashboard-grid__lower">
                    <PerformanceCard skill={skill.data} location={location} meta={vmeta} lead={lead} />
                    <WeightMap rows={varRows} locations={m.locations} selected={location} onSelect={(l) => update({ location: l })}
                      weights={weights.data} lead={lead} meta={vmeta} />
                  </div>

                  <ExtremeVerification extremes={extremes.data} lead={lead} />
                </div>

                <aside className="dashboard-grid__side">
                  <ModelWeights row={current} digits={vmeta.digits} />
                  <ExtremeWeatherAlert rows={rows} validTime={validTime} onSelect={(l, v) => update({ location: l, variable: v })} />
                  <WeatherRegime row={current} issueTime={time} />
                  {current && <LiveBlend key={`${current.location}|${variable}|${lead}|${current.timestamp}`} row={current} variable={variable} lead={lead} />}
                  <WorkflowCard meta={m} />
                </aside>
              </div>
            </>
          )}

        </Page>
    </>
  );
}

export default HistoricalPage;
