import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import DashboardCard from "../components/DashboardCard";
import IndiaMap from "../components/IndiaMap";
import { Page, SkeletonCard } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import VariableTabs from "../components/VariableTabs";
import { LIVE_MODELS, LIVE_MODEL_BY_KEY, VARIABLES, pct, placeUrl } from "../format";
import { useCities } from "../live";

const DAYS = [0, 1, 2, 3, 4, 5, 6, 7];

function WeightsPage() {
  const [variable, setVariable] = useState("temperature_2m_c");
  const [day, setDay] = useState(1);
  const cities = useCities();
  const navigate = useNavigate();
  const d = cities.data;
  const ready = (d?.cities || []).filter((c) => c.status === "ready");

  const points = ready.map((c) => {
    const dom = c.summary.dominant[variable]?.[String(day)];
    const m = dom && LIVE_MODEL_BY_KEY[dom.model];
    return {
      id: c.label, latitude: c.place.latitude, longitude: c.place.longitude, color: m ? m.color : "#cbd5e1",
      radius: dom ? 6 + dom.weight * 10 : 6, label: `${c.name}: ${m ? m.label + " " + pct(dom.weight) : "no data"}`,
      detail: dom ? LIVE_MODELS.map((x) => `${x.short} ${pct(dom.weights[x.key] ?? 0)}`).join(" · ") : null,
      onClick: () => navigate(placeUrl(c.place)),
    };
  });

  const counts = LIVE_MODELS.map((m) => ({
    ...m, n: ready.filter((c) => c.summary.dominant[variable]?.[String(day)]?.model === m.key).length,
  }));

  return (
    <>
      <PageHeader eyebrow="LIVE / MODEL WEIGHT MAPS" title="Which model to trust, where"
        badge={<SourceBadge kind="live" detail={d ? `${d.ready}/${d.total} cities` : "loading"} />} />
      <Page>
        <div className="page-intro">
          <div>
            <span className="eyebrow">WEIGHTS LEARNED PER CITY, VARIABLE AND LEAD DAY FROM VERIFIED HISTORY</span>
            <h2>{VARIABLES[variable].label} · lead day {day}</h2>
          </div>
          <VariableTabs value={variable} onChange={setVariable} />
        </div>

        <div className="segmented lead-picker" role="tablist" aria-label="Lead day">
          {DAYS.map((x) => (
            <button key={x} type="button" role="tab" aria-selected={x === day} className={x === day ? "is-active" : ""} onClick={() => setDay(x)}>
              {x === 0 ? "0–24 h" : `Day ${x}`}
            </button>
          ))}
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Weight map" icon="map" subtitle="Colour = model with the largest blend weight · size = how dominant it is · hover for all weights">
              {!d ? <SkeletonCard lines={0} height={420} /> : (
                <IndiaMap points={points} ariaLabel="Map of the dominant forecast model per city"
                  legend={LIVE_MODELS.map((m) => <span key={m.key}><i style={{ background: m.color }} />{m.label} ({m.kind})</span>)} />
              )}
            </DashboardCard>

            <DashboardCard title="Dominant model by lead day" icon="grid_on" subtitle={`${VARIABLES[variable].label}: largest mean weight per city and lead day`}>
              {!d ? <SkeletonCard lines={6} height={0} /> : (
                <div className="table-scroll table-scroll--tall">
                  <table className="weight-grid">
                    <thead><tr><th />{DAYS.map((x) => <th key={x}>{x === 0 ? "0–24h" : `D${x}`}</th>)}</tr></thead>
                    <tbody>
                      {ready.map((c) => (
                        <tr key={c.label}>
                          <th><Link to={placeUrl(c.place)}>{c.name}</Link></th>
                          {DAYS.map((x) => {
                            const dom = c.summary.dominant[variable]?.[String(x)];
                            if (!dom) return <td key={x} />;
                            const m = LIVE_MODEL_BY_KEY[dom.model];
                            return (
                              <td key={x} title={LIVE_MODELS.map((mm) => `${mm.label} ${pct(dom.weights[mm.key] ?? 0)}`).join(" · ")}>
                                <span className="weight-grid__cell" style={{ "--c": m.color, "--a": Math.max(0.12, (dom.weight - 0.25) * 1.3) }}>
                                  <i style={{ background: m.color }} />{m.short} {pct(dom.weight)}
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </DashboardCard>
          </div>

          <aside className="dashboard-grid__side">
            <DashboardCard title="Tally" icon="leaderboard" subtitle={`Cities where each model dominates · ${VARIABLES[variable].label.toLowerCase()}, lead day ${day}`}>
              <ul className="tally">
                {counts.map((m) => (
                  <li key={m.key}>
                    <span><i className="swatch" style={{ background: m.color }} />{m.label}<small className="muted"> {m.kind}</small></span>
                    <strong>{m.n}</strong>
                  </li>
                ))}
              </ul>
              <p className="card-caption">Out of {ready.length} cities computed so far. A dominant model can still hold well under half the weight: open a city to see the full split.</p>
            </DashboardCard>
            <DashboardCard title="2025 replay weight maps" icon="history" subtitle="The research archive (5 Maharashtra sites, 6/12/24 h leads)">
              <p className="card-caption">Weights by location, lead time and season for the 2025 hindcast experiment live on the <Link to="/historical">2025 Replay</Link> page.</p>
            </DashboardCard>
          </aside>
        </div>
      </Page>
    </>
  );
}

export default WeightsPage;
