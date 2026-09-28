import { useState } from "react";
import { Link } from "react-router-dom";
import { qs, useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import { Bar, Page, SkeletonCard } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import PerformanceCard from "../components/PerformanceCard";
import VariableTabs from "../components/VariableTabs";
import { LIVE_MODEL_BY_KEY, VARIABLES, fmt, placeUrl } from "../format";
import { useCities } from "../live";

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null;
};

function PerformancePage() {
  const [variable, setVariable] = useState("temperature_2m_c");
  const [histLead, setHistLead] = useState(12);
  const cities = useCities();
  const ready = (cities.data?.cities || []).filter((c) => c.status === "ready");
  const meta = VARIABLES[variable];

  // gain = 100 * (1 - blend MAE / best single-model MAE), per city and lead day
  const rows = ready.flatMap((c) => (c.summary.skill?.[variable] || []).map((s) => ({
    city: c, ...s, gain: s.best_member_mae ? 100 * (1 - s.blended / s.best_member_mae) : null,
  })));
  const days = [...new Set(rows.map((r) => r.lead_day))].sort((a, b) => a - b);
  const byDay = days.map((day) => {
    const r = rows.filter((x) => x.lead_day === day && x.gain !== null);
    return { day, n: r.length, wins: r.filter((x) => x.gain >= 0).length, median: median(r.map((x) => x.gain)) };
  });
  const total = byDay.reduce((a, b) => a + b.n, 0);
  const wins = byDay.reduce((a, b) => a + b.wins, 0);

  const hist = useApi("/skill" + qs({ variable, lead: histLead }));

  return (
    <>
      <PageHeader eyebrow="PERFORMANCE / VERIFIED AGAINST ERA5" title="Does blending beat the best model?"
        badge={<SourceBadge kind="live" detail={`${ready.length} cities scored`} />} />
      <Page>
        <div className="page-intro">
          <div>
            <span className="eyebrow">OUT-OF-SAMPLE · SCORED ON DAYS NEVER USED TO FIT OR CHOOSE THE WEIGHTS</span>
            <h2>{meta.label}</h2>
          </div>
          <VariableTabs value={variable} onChange={setVariable} />
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Live: blend vs best single model" icon="analytics"
              subtitle="Per lead day across all computed cities. Gain = MAE reduction relative to whichever single model was best at that city."
              action={<span className="card-tag">{wins}/{total} CITY·LEAD CASES WON</span>}>
              {!cities.data ? <SkeletonCard lines={5} height={0} /> : total === 0 ? <div className="chart-empty">No cities scored yet.</div> : (
                <div className="lead-skill">
                  {byDay.map((b) => (
                    <div key={b.day} className="lead-skill__row">
                      <span className="lead-skill__day">{b.day === 0 ? "0–24 h" : `Day ${b.day}`}</span>
                      <Bar value={b.wins} max={b.n} color={b.wins / b.n >= 0.5 ? "#4a3aa7" : "#94a3b8"} />
                      <span className="lead-skill__num">{b.wins}/{b.n} cities</span>
                      <span className={"lead-skill__gain" + (b.median >= 0 ? " is-good" : " is-bad")}>median {b.median >= 0 ? "+" : ""}{fmt(b.median, 1)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </DashboardCard>

            <DashboardCard title="City by city" icon="table_rows" subtitle="Lead day 1 · MAE on the held-out window">
              {!cities.data ? <SkeletonCard lines={6} height={0} /> : (
                <div className="table-scroll table-scroll--tall">
                  <table className="data-table">
                    <thead><tr><th>City</th><th>Best single model</th><th>Its MAE</th><th>Blend MAE</th><th>Gain</th></tr></thead>
                    <tbody>
                      {rows.filter((r) => r.lead_day === 1).sort((a, b) => b.gain - a.gain).map((r) => (
                        <tr key={r.city.label}>
                          <td><Link to={placeUrl(r.city.place)}>{r.city.name}</Link></td>
                          <td><i className="swatch" style={{ background: LIVE_MODEL_BY_KEY[r.best_member].color }} />{LIVE_MODEL_BY_KEY[r.best_member].label}</td>
                          <td>{fmt(r.best_member_mae, 3)}</td>
                          <td>{fmt(r.blended, 3)}</td>
                          <td className={r.gain >= 0 ? "gain-good" : "gain-bad"}>{r.gain >= 0 ? "+" : ""}{fmt(r.gain, 1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </DashboardCard>
          </div>

          <aside className="dashboard-grid__side">
            <DashboardCard title="Reading this honestly" icon="info">
              <ul className="notes">
                <li>Each city’s blend is scored on its most recent 21 verified days, which were never used to fit or pick its weights.</li>
                <li>Temperature and wind usually gain the most. For rainfall, blending often only ties the best single model, and sometimes loses.</li>
                <li>ERA5 truth lags about 6 days, so the scored window ends about a week ago.</li>
              </ul>
            </DashboardCard>

            <div className="section-label"><SourceBadge kind="historical" /></div>
            <div className="segmented" role="tablist" aria-label="Replay lead time">
              {[6, 12, 24].map((l) => (
                <button type="button" key={l} role="tab" aria-selected={l === histLead} className={l === histLead ? "is-active" : ""} onClick={() => setHistLead(l)}>{l} h</button>
              ))}
            </div>
            {hist.data ? <PerformanceCard skill={hist.data} location="Mumbai" meta={meta} lead={histLead} />
              : hist.error ? <div className="chart-empty">{hist.error.message}</div> : <SkeletonCard lines={5} height={0} />}
          </aside>
        </div>
      </Page>
    </>
  );
}

export default PerformancePage;
