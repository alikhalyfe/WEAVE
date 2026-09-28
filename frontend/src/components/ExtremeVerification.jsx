import DashboardCard from "./DashboardCard";
import { BLEND, MODELS, fmt } from "../format";

const SOURCES = [
  ...MODELS.map((m) => ({ key: m.key, label: m.key === "ai_model" ? "AI model" : m.label, color: m.color })),
  { key: "blended_raw", label: "Blend @ p95", color: BLEND.color },
  { key: "guidance", label: "Guidance", color: BLEND.color, strong: true },
];

function ExtremeVerification({ extremes, lead }) {
  const rows = (extremes?.verification || []).filter((r) => r.lead_time_hours === lead);
  const events = [...new Set(rows.map((r) => r.event))];
  const scales = Object.fromEntries((extremes?.scales || []).filter((s) => s.lead_time_hours === lead).map((s) => [s.target_variable, s.scale]));

  return (
    <DashboardCard id="extreme-events" title="Extreme Event Skill · 2025" icon="thunderstorm" className="extreme-card"
      subtitle={`Events = local p95 exceedance · ${lead}h lead · CSI higher is better`}
      action={<span className="card-tag">POD · FAR · CSI</span>}>
      <div className="extreme-grid">
        {events.map((ev) => {
          const evRows = rows.filter((r) => r.event === ev);
          const best = Math.max(...evRows.map((r) => r.csi));
          const variable = evRows[0]?.target_variable;
          return (
            <div className="extreme-block" key={ev}>
              <div className="extreme-block__head">
                <strong>{ev}</strong>
                <span>{evRows[0]?.observed_events.toLocaleString()} observed · guidance at {fmt((scales[variable] ?? 1) * 100, 0)}% of p95</span>
              </div>
              <div className="csi-row csi-row--head" aria-hidden="true">
                <span /><span /><span className="csi-row__num">POD</span><span className="csi-row__num">FAR</span><span className="csi-row__num">CSI</span>
              </div>
              {SOURCES.map((s) => {
                const r = evRows.find((x) => x.source === s.key);
                if (!r) return null;
                return (
                  <div className={"csi-row" + (s.strong ? " is-strong" : "")} key={s.key}
                    title={`POD ${fmt(r.pod, 2)} · FAR ${fmt(r.far, 2)} · CSI ${fmt(r.csi, 3)} · frequency bias ${fmt(r.frequency_bias, 2)}`}>
                    <span className="csi-row__name"><i style={{ background: s.color }} />{s.label}</span>
                    <div className="csi-row__track"><span style={{ width: (best ? (r.csi / best) * 100 : 0) + "%", background: s.color }} /></div>
                    <span className="csi-row__num">{fmt(r.pod, 2)}</span>
                    <span className="csi-row__num">{fmt(r.far, 2)}</span>
                    <strong className="csi-row__num">{fmt(r.csi, 3)}</strong>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
      <p className="card-caption">
        Columns: probability of detection, false-alarm ratio, critical success index. Guidance thresholds are tuned on the
        2024 hindcast only, then frozen for 2025.
      </p>
    </DashboardCard>
  );
}

export default ExtremeVerification;
