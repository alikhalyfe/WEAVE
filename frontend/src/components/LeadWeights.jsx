import { motion } from "motion/react";
import { CONFIG_LABELS, LIVE_MODELS, METHOD_LABELS, pct } from "../format";

/** Mean blend weight of each member per lead day, as animated stacked bars. */
function LeadWeights({ points, chosen }) {
  const days = [...new Set(points.map((p) => p.lead_day))].sort((a, b) => a - b);
  const byDay = days.map((day) => {
    const ws = points.filter((p) => p.lead_day === day).map((p) => p.weights);
    const mean = Object.fromEntries(LIVE_MODELS.map((m) => [m.key, ws.reduce((s, w) => s + (w[m.key] ?? 0), 0) / ws.length]));
    const c = chosen.find((x) => x.lead_day === day);
    return { day, mean, c };
  });

  return (
    <div className="lead-weights">
      {byDay.map(({ day, mean, c }) => (
        <div className="lead-weights__row" key={day}>
          <span className="lead-weights__day">Day {day}</span>
          <div className="lead-weights__bar" role="img"
            aria-label={`Day ${day}: ` + LIVE_MODELS.map((m) => `${m.label} ${pct(mean[m.key])}`).join(", ")}>
            {LIVE_MODELS.map((m) => mean[m.key] > 0.005 && (
              <motion.span key={m.key} style={{ background: m.color }} title={`${m.label} ${pct(mean[m.key])}`}
                initial={{ width: 0 }} animate={{ width: mean[m.key] * 100 + "%" }} transition={{ duration: 0.6, delay: day * 0.04 }}>
                {mean[m.key] >= 0.14 && <em>{m.short} {pct(mean[m.key])}</em>}
              </motion.span>
            ))}
          </div>
          <span className="lead-weights__method" title={c ? CONFIG_LABELS[c.config] : ""}>{c ? METHOD_LABELS[c.method] : "—"}</span>
        </div>
      ))}
      <div className="weight-map__legend">
        {LIVE_MODELS.map((m) => <span key={m.key}><i style={{ background: m.color }} />{m.label} ({m.kind})</span>)}
      </div>
    </div>
  );
}

export default LeadWeights;
