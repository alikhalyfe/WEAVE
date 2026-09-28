import DashboardCard from "./DashboardCard";
import { VARIABLES, fmt, fmtTime, pct } from "../format";

function severity(p) {
  if (p >= 0.66) return { key: "high", label: "HIGH", icon: "error" };
  if (p >= 0.33) return { key: "moderate", label: "MODERATE", icon: "warning" };
  return { key: "low", label: "LOW", icon: "info" };
}

function ExtremeWeatherAlert({ rows, validTime, onSelect }) {
  const alerts = (rows || [])
    .filter((r) => r.guidance_event)
    .sort((a, b) => b.event_probability - a.event_probability);

  return (
    <DashboardCard id="alerts" title="Extreme Weather Guidance" icon="warning" className="alert-card"
      subtitle={`Valid ${fmtTime(validTime)} · all locations`}>
      {alerts.length === 0 && (
        <div className="alert-empty">
          <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
          No heavy-rain, heat or high-wind signal for this time.
        </div>
      )}
      <ul className="alert-list">
        {alerts.map((r) => {
          const v = VARIABLES[r.target_variable];
          const s = severity(r.event_probability);
          const verified = r.observed_event === null ? null : r.observed_event ? "Occurred" : "Did not occur";
          return (
            <li key={r.location + r.target_variable} className={"alert-item alert-item--" + s.key}>
              <button type="button" onClick={() => onSelect(r.location, r.target_variable)}>
                <span className="alert-item__head">
                  <span className="alert-card__severity"><span className="material-symbols-outlined" aria-hidden="true">{s.icon}</span>{s.label}</span>
                  <span className="alert-card__probability">{pct(r.event_probability)} model agreement</span>
                </span>
                <strong>{v.event} · {r.location}</strong>
                <span className="alert-item__detail">
                  Blend {fmt(r.blended, v.digits)} {v.unit} vs guidance threshold {fmt(r.guidance_threshold, v.digits)} (p95 {fmt(r.event_threshold, v.digits)})
                </span>
                {verified && <span className={"alert-item__verified" + (r.observed_event ? " is-hit" : "")}>Verification: {verified} (obs {fmt(r.actual_value, v.digits)})</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </DashboardCard>
  );
}

export default ExtremeWeatherAlert;
