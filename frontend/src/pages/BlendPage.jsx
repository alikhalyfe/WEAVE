import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { api, useApi } from "../api";
import DashboardCard from "../components/DashboardCard";
import { AnimatedNumber, Bar, Page } from "../components/Motion";
import PageHeader, { SourceBadge } from "../components/PageHeader";
import { CONFIG_LABELS, LEVEL_LABELS, METHOD_LABELS, MODELS, VARIABLES, fmt, pct } from "../format";

const SEASONS = ["Winter", "Summer", "Monsoon", "Post-Monsoon"];
const REGIMES = ["Normal", "Heavy Rain", "Heat", "High Wind"];

/** Blend user-supplied member values with weights learned from the 2025 archive. */
function BlendPage() {
  const meta = useApi("/meta");
  const [form, setForm] = useState({
    location: "Mumbai", target_variable: "precipitation_mm", lead_time_hours: 12, season: "Monsoon",
    weather_regime: "Normal", issue_hour: 6, model_a: "", model_b: "", ai_model: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const v = VARIABLES[form.target_variable];

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const forecasts = Object.fromEntries(MODELS.map((m) => [m.key, form[m.key] === "" ? null : Number(form[m.key])]));
      setResult(await api("/blend", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          location: form.location, target_variable: form.target_variable, lead_time_hours: Number(form.lead_time_hours),
          season: form.season, weather_regime: form.weather_regime, issue_hour: Number(form.issue_hour), forecasts,
        }),
      }));
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="RESEARCH / BLEND TOOL" title="Blend your own forecasts" badge={<SourceBadge kind="historical" detail="weights from the 2025 archive" />} />
      <Page>
        <div className="dashboard-grid">
          <div className="dashboard-grid__main">
            <DashboardCard title="Inputs" icon="edit_note" subtitle="Enter each model’s forecast. Leave one empty to blend without it." action={<span className="card-tag">POST /api/blend</span>}>
              <form className="blend-form" onSubmit={submit}>
                <label>Location
                  <select value={form.location} onChange={set("location")}>
                    {(meta.data?.locations || []).map((l) => <option key={l.location}>{l.location}</option>)}
                  </select>
                </label>
                <label>Variable
                  <select value={form.target_variable} onChange={set("target_variable")}>
                    {Object.entries(VARIABLES).map(([k, x]) => <option key={k} value={k}>{x.label} ({x.unit})</option>)}
                  </select>
                </label>
                <label>Lead time
                  <select value={form.lead_time_hours} onChange={set("lead_time_hours")}>{[6, 12, 24].map((l) => <option key={l} value={l}>{l} hours</option>)}</select>
                </label>
                <label>Season
                  <select value={form.season} onChange={set("season")}>{SEASONS.map((s) => <option key={s}>{s}</option>)}</select>
                </label>
                <label>Weather regime at issue
                  <select value={form.weather_regime} onChange={set("weather_regime")}>{REGIMES.map((s) => <option key={s}>{s}</option>)}</select>
                </label>
                <label>Issue hour (UTC)
                  <input type="number" min="0" max="23" value={form.issue_hour} onChange={set("issue_hour")} />
                </label>
                {MODELS.map((m) => (
                  <label key={m.key}><span><i className="swatch" style={{ background: m.color }} />{m.label} forecast ({v.unit})</span>
                    <input type="number" step="any" inputMode="decimal" value={form[m.key]} onChange={set(m.key)} placeholder="missing" />
                  </label>
                ))}
                <button type="submit" className="primary-button" disabled={busy}>
                  <span className="material-symbols-outlined" aria-hidden="true">merge</span>{busy ? "Blending…" : "Blend"}
                </button>
              </form>
              {error && <p className="form-error" role="alert">{error}</p>}
            </DashboardCard>
          </div>
          <aside className="dashboard-grid__side">
            <AnimatePresence mode="wait">
              {result ? (
                <motion.div key={JSON.stringify(result)} initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}>
                  <DashboardCard title="Blended forecast" icon="merge" subtitle={`${form.location} · ${v.label} · +${form.lead_time_hours} h`}>
                    <div className="live-result__value big"><strong><AnimatedNumber value={result.blended_forecast} digits={v.digits} /></strong><span>{v.unit}</span></div>
                    <div className="weight-list">
                      {MODELS.map((m) => (
                        <div className="weight-row" key={m.key}>
                          <div className="weight-row__top"><span className="weight-row__name"><i style={{ background: m.color }} />{m.label}</span><strong>{pct(result.weights[m.key])}</strong></div>
                          <Bar value={result.weights[m.key]} color={m.color} className="weight-track" />
                          <div className="weight-row__meta">historical MAE {fmt(result.historical_mae[m.key], 3)} · bias correction {fmt(-result.bias_correction[m.key], 3)}</div>
                        </div>
                      ))}
                    </div>
                    <dl className="kv-list">
                      <div><dt>Method</dt><dd>{METHOD_LABELS[result.method]}</dd></div>
                      <div><dt>Configuration</dt><dd>{CONFIG_LABELS[result.config]}</dd></div>
                      <div><dt>Weights learned at</dt><dd>{LEVEL_LABELS[result.fallback_level]}</dd></div>
                      <div><dt>Verified cases</dt><dd>{result.n_history.toLocaleString()}</dd></div>
                    </dl>
                  </DashboardCard>
                </motion.div>
              ) : (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <DashboardCard title="How it works" icon="info">
                    <p className="card-caption">This uses the research archive: weights learned from every verified 2025 forecast of the Persistence, Random Forest and gradient-boosting members at the 5 Maharashtra sites. The method and configuration are the ones selected for this variable and lead on the 2024 hindcast.</p>
                  </DashboardCard>
                </motion.div>
              )}
            </AnimatePresence>
          </aside>
        </div>
      </Page>
    </>
  );
}

export default BlendPage;
