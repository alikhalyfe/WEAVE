import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import DayScrubber from "../components/DayScrubber";
import IndiaGridMap from "../components/IndiaGridMap";
import { Page, Rise, SkeletonCard, Stagger } from "../components/Motion";
import OfficialAlerts from "../components/OfficialAlerts";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import SearchBox from "../components/SearchBox";
import VariableTabs from "../components/VariableTabs";
import { HAZARD_ICON, LEVEL_STYLE, LIVE_MODELS, ago, fmt, pct, placeUrl } from "../format";
import { useCities } from "../live";

const LAYERS = [
  { key: "forecast", label: "Blended forecast", icon: "layers" },
  { key: "model", label: "Most-trusted model", icon: "tune" },
];

function OverviewPage() {
  const [variable, setVariable] = useState("precipitation_mm");
  const [layer, setLayer] = useState("forecast");
  const [day, setDay] = useState(0);
  const setDayCb = useCallback((d) => setDay(d), []);
  const navigate = useNavigate();
  const cities = useCities();
  const grid = useApi("/live/grid", { pollMs: 6000, poll: (g) => g.status !== "ready" });
  const boundary = useApi("/live/boundary");
  const official = useApi("/live/official-alerts");
  const g = grid.data?.status === "ready" ? grid.data : null;
  const ready = (cities.data?.cities || []).filter((c) => c.status === "ready");
  const hazards = ready
    .flatMap((c) => c.summary.alerts.filter((a) => a.level !== "notice").map((a) => ({ ...a, city: c })))
    .sort((a, b) => (a.level === b.level ? (b.probability ?? 1) - (a.probability ?? 1) : a.level === "warning" ? -1 : 1));

  return (
    <>
      <PageHeader eyebrow="LIVE · INDIA" title="India weather, blended from 5 models" search={false}
        badge={<SourceBadge kind="live" detail={g ? `grid ${ago(g.fetched_at)}` : cities.data ? `${cities.data.ready}/${cities.data.total} cities` : "connecting"} />} />
      <Page>
        {cities.error && <div className="banner banner--error" role="alert"><span className="material-symbols-outlined" aria-hidden="true">cloud_off</span><div><strong>Can’t reach the WEAVE API.</strong> {cities.error.message}</div></div>}

        <section className="hero">
          <div className="hero__text">
            <h2>One forecast, built from the best of five.</h2>
            <p>
              WEAVE weighs {LIVE_MODELS.map((m) => m.short).join(", ")} for every place, season, weather regime and day ahead, using how
              each model has actually performed there against ERA5 observations.
            </p>
          </div>
          <div className="hero__search"><SearchBox /></div>
        </section>

        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title={layer === "forecast" ? "Forecast map" : "Model weight map"} icon="map"
              subtitle={layer === "forecast"
                ? "Blended daily totals / maxima on a 1.5° grid. Rain in IMD categories."
                : "Which model the blend leans on most, region by region. Weights come from the nearest verified cities."}
              action={<div className="segmented segmented--tight" role="tablist" aria-label="Map layer">
                {LAYERS.map((l) => (
                  <button key={l.key} type="button" role="tab" aria-selected={layer === l.key} className={layer === l.key ? "is-active" : ""} onClick={() => setLayer(l.key)}>
                    <span className="material-symbols-outlined" aria-hidden="true">{l.icon}</span>{l.label}
                  </button>
                ))}
              </div>}>
              <div className="map-controls">
                <VariableTabs value={variable} onChange={setVariable} />
                {g && <DayScrubber dates={g.dates} value={day} onChange={setDayCb} />}
              </div>
              {!g ? (
                <div className="map-building">
                  <SkeletonCard lines={0} height={440} />
                  <p className="progress-note" role="status">
                    <span className="material-symbols-outlined spin" aria-hidden="true">progress_activity</span>
                    Building the India grid: fetching 5 models for 124 grid points and learning regional weights
                    {cities.data ? ` (${cities.data.ready}/${cities.data.total} reference cities ready)` : ""}.
                  </p>
                </div>
              ) : (
                <IndiaGridMap grid={g} boundary={boundary.data} variable={variable} day={day} layer={layer}
                  cities={cities.data?.cities || []} official={official.data?.alerts || []}
                  onCity={(c) => navigate(placeUrl(c.place))} />
              )}
              {g && <p className="card-caption">{g.note} Weights learned at {g.weight_sources.length} cities. Click a city for its full forecast.</p>}
            </DashboardCard>

            <DashboardCard title="Cities today" icon="location_city" subtitle="Plain-language forecast for each tracked city · click for the full week">
              {!cities.data ? <SkeletonCard lines={4} height={0} /> : (
                <Stagger className="city-cards">
                  {cities.data.cities.map((c) => {
                    const today = c.summary?.outlook?.[0];
                    const warn = c.summary?.alerts?.find((a) => a.level !== "notice");
                    return (
                      <Rise key={c.label}>
                        {c.status === "ready" && today ? (
                          <Link to={placeUrl(c.place)} className={"city-card" + (warn ? " has-warning" : "")}>
                            <span className="city-card__name">{c.name}<small>{c.state}</small></span>
                            <span className="material-symbols-outlined city-card__icon" aria-hidden="true">{today.icon}</span>
                            <span className="city-card__temp">{fmt(today.high, 0)}°<small>/{fmt(today.low, 0)}°</small></span>
                            <span className="city-card__words">{today.headline}</span>
                            {today.rain_chance != null && <span className="city-card__rain">{pct(today.rain_chance)} rain</span>}
                            {warn && <span className="city-card__warn"><span className="material-symbols-outlined" aria-hidden="true">{HAZARD_ICON[warn.type]}</span>{warn.label}</span>}
                          </Link>
                        ) : (
                          <div className="city-card is-pending">
                            <span className="city-card__name">{c.name}<small>{c.state}</small></span>
                            <span className="muted">{c.status === "error" ? "Unavailable" : "Learning model skill…"}</span>
                          </div>
                        )}
                      </Rise>
                    );
                  })}
                </Stagger>
              )}
            </DashboardCard>
          </div>

          <aside className="dashboard-grid__side">
            <DashboardCard title="Official warnings" icon="campaign" className="official-card"
              subtitle={official.data ? `NDMA SACHET · IMD, CWC and state authorities · updated ${ago(official.data.fetched_at)}` : "NDMA SACHET"}
              action={official.data && <span className="card-tag">{official.data.alerts.length} ACTIVE</span>}>
              {official.error ? <p className="muted">Official feed unavailable right now.</p>
                : !official.data ? <SkeletonCard lines={3} height={0} />
                  : <OfficialAlerts alerts={official.data.alerts} limit={6} />}
            </DashboardCard>

            <DashboardCard title="WEAVE hazard outlook" icon="crisis_alert" className="alert-card"
              subtitle="Heat wave, heavy rain or high wind in the next 3 days: IMD-style rules on the blend, plus the 51-member ensemble">
              {!cities.data ? <SkeletonCard lines={3} height={0} /> : hazards.length === 0 ? (
                <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>No heat-wave, heavy-rain or high-wind signals across {ready.length} cities.</div>
              ) : (
                <ul className="alert-list">
                  {hazards.slice(0, 8).map((h) => (
                    <li key={h.city.label + h.type + h.date} className={"alert-item alert-item--" + (h.level === "warning" ? "high" : "moderate")}>
                      <button type="button" onClick={() => navigate(placeUrl(h.city.place))}>
                        <span className="alert-item__head">
                          <span className="alert-card__severity" style={{ color: LEVEL_STYLE[h.level].color }}>{LEVEL_STYLE[h.level].label.toUpperCase()}</span>
                          <span className="alert-card__probability">{h.day_label}</span>
                        </span>
                        <strong>{h.label} · {h.city.name}</strong>
                        <span className="alert-item__detail">{h.sentence}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </DashboardCard>
          </aside>
        </div>
      </Page>
    </>
  );
}

export default OverviewPage;
