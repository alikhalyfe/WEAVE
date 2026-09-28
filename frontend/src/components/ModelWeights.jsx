import DashboardCard from "./DashboardCard";
import { CONFIG_LABELS, LEVEL_LABELS, METHOD_LABELS, MODELS, fmt, pct } from "../format";

function ModelWeights({ row, digits }) {
  if (!row) return null;
  return (
    <DashboardCard
      id="weights"
      title="Adaptive Model Blending"
      icon="tune"
      subtitle="Weights for the selected location, variable and lead time"
      className="weights-card"
      action={<span className="card-tag">{(METHOD_LABELS[row.blend_method] || row.blend_method).toUpperCase()}</span>}
    >
      <div className="weight-list">
        {MODELS.map((m) => {
          const w = row["weight_" + m.key];
          return (
            <div className="weight-row" key={m.key}>
              <div className="weight-row__top">
                <span className="weight-row__name"><i style={{ background: m.color }} />{m.label}</span>
                <strong>{pct(w)}</strong>
              </div>
              <div className="weight-track" role="img" aria-label={`${m.label} weight ${pct(w)}`}>
                <span style={{ width: w * 100 + "%", background: m.color }} />
              </div>
              <div className="weight-row__meta">
                forecast {fmt(row[m.key + "_forecast"], digits)} · bias correction {fmt(-row["bias_" + m.key], digits)}
              </div>
            </div>
          );
        })}
      </div>
      <dl className="kv-list">
        <div><dt>Configuration</dt><dd>{CONFIG_LABELS[row.blend_config]}</dd></div>
        <div><dt>Conditioning level</dt><dd>{LEVEL_LABELS[row.fallback_level] || row.fallback_level}</dd></div>
        <div><dt>Verified cases used</dt><dd>{row.n_history.toLocaleString()}</dd></div>
        <div><dt>Regime at issue</dt><dd>{row.weather_regime}</dd></div>
      </dl>
    </DashboardCard>
  );
}

export default ModelWeights;
