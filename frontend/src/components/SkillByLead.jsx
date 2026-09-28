import { motion } from "motion/react";
import { useState } from "react";
import { BLEND, LIVE_MODELS, fmt } from "../format";

const W = 560;
const H = 220;
const PAD = { top: 12, right: 14, bottom: 28, left: 44 };

/** Out-of-sample MAE per lead day for every member and the blend (lower is better). */
function SkillByLead({ skill, digits = 2, unit }) {
  const [table, setTable] = useState(false);
  const sources = [
    ...LIVE_MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color, width: 1.6 })),
    { key: "equal_mean", label: "Simple average", color: "#94a3b8", width: 1.6, dash: "4 3" },
    { key: "blended", label: BLEND.label, color: BLEND.color, width: 3 },
  ];
  const days = [...new Set(skill.map((s) => s.lead_day))].sort((a, b) => a - b);
  if (!days.length) return <div className="chart-empty">No verified history yet for this place.</div>;
  const val = (src, d) => skill.find((s) => s.source === src && s.lead_day === d)?.mae ?? null;
  const all = skill.map((s) => s.mae);
  const hi = Math.max(...all) * 1.08;
  const sx = (d) => PAD.left + ((d - days[0]) / (days[days.length - 1] - days[0] || 1)) * (W - PAD.left - PAD.right);
  const sy = (v) => PAD.top + (1 - v / hi) * (H - PAD.top - PAD.bottom);
  const ticks = [0, hi / 3, (2 * hi) / 3].map((t) => +t.toPrecision(2));

  return (
    <div className="forecast-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mean absolute error by lead day for each model and the blend">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={sy(t)} y2={sy(t)} className="chart-grid" />
            <text x={PAD.left - 6} y={sy(t) + 3} textAnchor="end" className="chart-tick">{fmt(t, digits)}</text>
          </g>
        ))}
        {days.map((d) => <text key={d} x={sx(d)} y={H - 8} textAnchor="middle" className="chart-tick">day {d}</text>)}
        {sources.map((s) => {
          const pts = days.map((d) => [d, val(s.key, d)]).filter(([, v]) => v !== null);
          if (!pts.length) return null;
          const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${sx(x).toFixed(1)} ${sy(y).toFixed(1)}`).join("");
          return (
            <g key={s.key}>
              <motion.path d={d} fill="none" stroke={s.color} strokeWidth={s.width} strokeDasharray={s.dash} strokeLinecap="round"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8 }} />
              {pts.map(([x, y]) => <circle key={x} cx={sx(x)} cy={sy(y)} r={s.key === "blended" ? 3.5 : 2.5} fill={s.color} stroke="#fff" strokeWidth="1.5"><title>{`${s.label}, day ${x}: MAE ${fmt(y, 3)} ${unit}`}</title></circle>)}
            </g>
          );
        })}
      </svg>
      <div className="chart-legend">
        {sources.map((s) => (
          <span key={s.key}><i className="legend-line" style={{ background: s.dash ? `repeating-linear-gradient(90deg, ${s.color} 0 4px, transparent 4px 7px)` : s.color, height: s.width }} />{s.label}</span>
        ))}
        <button type="button" className="link-button" onClick={() => setTable((v) => !v)}>{table ? "Hide table" : "Table view"}</button>
      </div>
      {table && (
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Lead</th>{sources.map((s) => <th key={s.key}>{s.label}</th>)}<th>n</th></tr></thead>
            <tbody>
              {days.map((d) => (
                <tr key={d}><td>Day {d}</td>{sources.map((s) => <td key={s.key}>{fmt(val(s.key, d), 3)}</td>)}<td>{skill.find((x) => x.lead_day === d)?.n}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default SkillByLead;
