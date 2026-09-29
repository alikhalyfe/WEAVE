import DashboardCard from "./DashboardCard";
import { CONFIG_LABELS, METHOD_LABELS, VARIABLES } from "../format";

const STAGES = ["ERA5 ingest & validation", "Model A/B/AI forecasts", "Regime classification", "Rolling adaptive blend", "Method selection", "Skill & extremes verification", "API + dashboard"];

function WorkflowCard({ meta }) {
  if (!meta) return null;
  const generated = meta.generated_at?.replace("T", " ").replace("+00:00", " UTC");
  return (
    <DashboardCard id="workflow" title="2025 replay pipeline" icon="settings_suggest" className="workflow-card"
      subtitle={`Research archive, not the live blend · last rebuilt ${generated} · ${meta.runtime_seconds}s`}
      action={<span className="card-tag card-tag--historical">REPLAY · 2025</span>}>
      <ol className="workflow-stages">
        {STAGES.map((s) => <li key={s}>{s}</li>)}
      </ol>
      <code className="workflow-cmd">python -m src.workflow</code>
      <dl className="kv-list">
        <div><dt>Weights update</dt><dd>{meta.weights_update_frequency}</dd></div>
        <div><dt>Skill history</dt><dd>{meta.hindcast_period[0].slice(0, 4)} hindcast + verified {meta.evaluation_period[0].slice(0, 4)}</dd></div>
        <div><dt>Forecasts blended</dt><dd>{meta.rows.toLocaleString()}</dd></div>
      </dl>
      <details className="method-compare">
        <summary>Blend chosen per variable &amp; lead (on 2024 hindcast)</summary>
        <table className="data-table">
          <thead><tr><th>Variable</th><th>Lead</th><th>Method</th><th>Configuration</th></tr></thead>
          <tbody>
            {meta.selected_methods.map((s) => (
              <tr key={s.target_variable + s.lead_time_hours}>
                <td>{VARIABLES[s.target_variable].label}</td><td>{s.lead_time_hours}h</td><td>{METHOD_LABELS[s.method]}</td><td>{CONFIG_LABELS[s.config]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </DashboardCard>
  );
}

export default WorkflowCard;
