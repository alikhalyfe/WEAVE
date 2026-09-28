import DashboardCard from "./DashboardCard";
import { BLEND, MODELS, candidateLabel, fmt } from "../format";

const SOURCES = [
  ...MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color })),
  { key: "equal_mean", label: "Simple average", color: "#94a3b8" },
  { key: "blended", label: BLEND.label, color: BLEND.color },
];

function PerformanceCard({ skill, location, meta, lead }) {
  const overall = skill?.by_variable_lead || [];
  const local = (skill?.by_location || []).filter((r) => r.location === location);
  const pick = (rows, key) => rows.find((r) => r.source === key);
  const rows = SOURCES.map((s) => ({ ...s, all: pick(overall, s.key), here: pick(local, s.key) })).filter((r) => r.all);
  const max = Math.max(...rows.map((r) => r.all.mae), 1e-9);
  const blend = pick(overall, "blended");
  const methods = overall.filter((r) => r.source.includes(".")).sort((a, b) => a.mae - b.mae);

  return (
    <DashboardCard
      id="performance"
      title="Forecast Skill · 2025"
      icon="analytics"
      subtitle={`Mean absolute error, all 5 locations, ${lead}h lead · lower is better`}
      className="performance-card"
      action={<span className="card-tag">MAE · {meta.unit.toUpperCase()}</span>}
    >
      <div className="performance-list">
        {rows.map((r) => (
          <div className="performance-row" key={r.key} title={`${r.label}: MAE ${fmt(r.all.mae, 3)}, RMSE ${fmt(r.all.rmse, 3)}, bias ${fmt(r.all.bias, 3)}`}>
            <span className="performance-row__name"><i style={{ background: r.color }} />{r.label}</span>
            <div className="performance-row__track"><span style={{ width: (r.all.mae / max) * 100 + "%", background: r.color }} /></div>
            <strong>{fmt(r.all.mae, 3)}</strong>
          </div>
        ))}
      </div>
      {blend && (
        <div className={"performance-note" + (blend.mae_skill_pct > 0 ? "" : " is-neutral")}>
          <span className="material-symbols-outlined" aria-hidden="true">{blend.mae_skill_pct > 0 ? "auto_awesome" : "info"}</span>
          {blend.mae_skill_pct > 0
            ? `Blend beats the best single model by ${fmt(blend.mae_skill_pct, 1)}% MAE`
            : `Blend is within ${fmt(-blend.mae_skill_pct, 1)}% of the best single model`}
          {pick(local, "blended") && ` · ${location}: ${fmt(pick(local, "blended").mae_skill_pct, 1)}%`}
        </div>
      )}
      <details className="method-compare">
        <summary>Compare all {methods.length} blending candidates</summary>
        <table className="data-table">
          <thead><tr><th>Method</th><th>MAE</th><th>RMSE</th><th>vs best model</th></tr></thead>
          <tbody>
            {methods.map((r) => (
              <tr key={r.source}>
                <td>{candidateLabel(...r.source.split("."))}</td>
                <td>{fmt(r.mae, 3)}</td>
                <td>{fmt(r.rmse, 3)}</td>
                <td>{fmt(r.mae_skill_pct, 1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </DashboardCard>
  );
}

export default PerformanceCard;
