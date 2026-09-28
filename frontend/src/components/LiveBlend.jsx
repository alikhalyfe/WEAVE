import { useState } from "react";
import DashboardCard from "./DashboardCard";
import { api } from "../api";
import { CONFIG_LABELS, LEVEL_LABELS, METHOD_LABELS, MODELS, VARIABLES, fmt, pct } from "../format";

/** Operational tool: paste new model forecasts, get the adaptive blend.
 * The parent keys this component on the selected row, so it starts fresh
 * (pre-filled with that row's member forecasts) whenever the selection changes. */
function LiveBlend({ row, variable, lead }) {
  const meta = VARIABLES[variable];
  const [form, setForm] = useState(() =>
    Object.fromEntries(MODELS.map((m) => [m.key, row[m.key + "_forecast"]?.toFixed(meta.digits) ?? ""])),
  );
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const forecasts = Object.fromEntries(MODELS.map((m) => [m.key, form[m.key] === "" ? null : Number(form[m.key])]));
      setResult(await api("/blend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          location: row.location, season: row.season, weather_regime: row.weather_regime,
          target_variable: variable, lead_time_hours: lead, forecasts, issue_hour: Number(row.timestamp.slice(11, 13)),
        }),
      }));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <DashboardCard id="live-blend" title="Blend New Forecasts" icon="bolt" className="live-card"
      subtitle={`${row.location} · ${row.season} · ${row.weather_regime} · ${meta.label} +${lead}h`}
      action={<span className="card-tag">POST /api/blend</span>}>
      <form className="live-form" onSubmit={submit}>
        {MODELS.map((m) => (
          <label key={m.key}>
            <span><i style={{ background: m.color }} />{m.label}</span>
            <input type="number" step="any" inputMode="decimal" value={form[m.key] ?? ""} placeholder="missing"
              onChange={(e) => setForm({ ...form, [m.key]: e.target.value })} />
          </label>
        ))}
        <button type="submit" className="primary-button">
          <span className="material-symbols-outlined" aria-hidden="true">merge</span>Blend
        </button>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      {result && (
        <div className="live-result" aria-live="polite">
          <div className="live-result__value">
            <strong>{fmt(result.blended_forecast, meta.digits)}</strong><span>{meta.unit}</span>
          </div>
          <span className="muted">{METHOD_LABELS[result.method]} · {CONFIG_LABELS[result.config]} · {LEVEL_LABELS[result.fallback_level]} · {result.n_history.toLocaleString()} verified cases</span>
          <div className="live-result__weights">
            {MODELS.map((m) => (
              <span key={m.key}><i style={{ background: m.color }} />{m.short} {pct(result.weights[m.key])}</span>
            ))}
          </div>
        </div>
      )}
    </DashboardCard>
  );
}

export default LiveBlend;
