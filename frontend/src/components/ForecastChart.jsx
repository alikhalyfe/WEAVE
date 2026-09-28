import { useMemo, useState } from "react";
import { BLEND, MODELS, OBSERVED, fmt, fmtTime, toDate } from "../format";

const W = 800;
const H = 240;
const PAD = { top: 12, right: 12, bottom: 26, left: 44 };
const SERIES = [
  ...MODELS.map((m) => ({ ...m, col: m.key + "_forecast", width: 1.6 })),
  { ...BLEND, col: "blended", width: 3 },
  { ...OBSERVED, col: "actual_value", width: 1.6, dash: "5 4" },
];

function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const step = 10 ** Math.floor(Math.log10(span / count));
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => span / s <= count) || step * 10;
  const ticks = [];
  for (let v = Math.ceil(min / nice) * nice; v <= max + 1e-9; v += nice) ticks.push(+v.toFixed(6));
  return ticks;
}

function ForecastChart({ points, issueTime, variable, meta, lead }) {
  const [hover, setHover] = useState(null);
  const [showTable, setShowTable] = useState(false);

  const geo = useMemo(() => {
    if (!points?.length) return null;
    const xs = points.map((p) => toDate(p.valid_time).getTime());
    const values = points.flatMap((p) => SERIES.map((s) => p[s.col])).filter((v) => v !== null && v !== undefined);
    let lo = Math.min(...values);
    let hi = Math.max(...values);
    if (variable !== "temperature_2m_c") lo = 0;
    const padV = (hi - lo) * 0.08 || 1;
    hi += padV;
    if (variable === "temperature_2m_c") lo -= padV;
    const x0 = xs[0];
    const x1 = xs[xs.length - 1];
    const sx = (t) => PAD.left + ((t - x0) / (x1 - x0 || 1)) * (W - PAD.left - PAD.right);
    const sy = (v) => PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);
    const paths = SERIES.map((s) => {
      let d = "";
      let pen = false;
      points.forEach((p, i) => {
        const v = p[s.col];
        if (v === null || v === undefined) {
          pen = false;
          return;
        }
        d += `${pen ? "L" : "M"}${sx(xs[i]).toFixed(1)} ${sy(v).toFixed(1)}`;
        pen = true;
      });
      return { ...s, d };
    });
    const dayTicks = [];
    points.forEach((p, i) => {
      if (p.valid_time.slice(11, 13) === "00") dayTicks.push({ x: sx(xs[i]), label: fmtTime(p.valid_time).split(",")[0] });
    });
    const issueValid = toDate(issueTime).getTime() + lead * 3600e3;
    return { xs, sx, sy, paths, yTicks: niceTicks(lo, hi), dayTicks, issueX: sx(issueValid), lo, hi };
  }, [points, variable, issueTime, lead]);

  if (!geo) return <div className="chart-empty">No forecasts for this selection.</div>;

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    let best = 0;
    geo.xs.forEach((t, i) => {
      if (Math.abs(geo.sx(t) - x) < Math.abs(geo.sx(geo.xs[best]) - x)) best = i;
    });
    setHover(best);
  };
  const hp = hover !== null ? points[hover] : null;

  return (
    <div className="forecast-chart">
      <div className="forecast-chart__plot">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${meta.label} forecasts by model, blend and observation`}
          onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {geo.yTicks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={geo.sy(t)} y2={geo.sy(t)} className="chart-grid" />
              <text x={PAD.left - 8} y={geo.sy(t) + 3} className="chart-tick" textAnchor="end">{fmt(t, meta.digits > 1 ? 1 : 0)}</text>
            </g>
          ))}
          {geo.dayTicks.map((t) => (
            <text key={t.x} x={t.x} y={H - 8} className="chart-tick" textAnchor="middle">{t.label}</text>
          ))}
          <line x1={geo.issueX} x2={geo.issueX} y1={PAD.top} y2={H - PAD.bottom} className="chart-issue" />
          <text x={geo.issueX + 4} y={PAD.top + 9} className="chart-issue-label">valid at selected issue +{lead}h</text>
          {geo.paths.map((p) => (
            <path key={p.col} d={p.d} fill="none" stroke={p.color} strokeWidth={p.width} strokeDasharray={p.dash}
              strokeLinejoin="round" strokeLinecap="round" opacity={p.col === "blended" || p.col === "actual_value" ? 1 : 0.8} />
          ))}
          {hp && (
            <g>
              <line x1={geo.sx(geo.xs[hover])} x2={geo.sx(geo.xs[hover])} y1={PAD.top} y2={H - PAD.bottom} className="chart-crosshair" />
              {SERIES.map((s) => hp[s.col] !== null && hp[s.col] !== undefined && (
                <circle key={s.col} cx={geo.sx(geo.xs[hover])} cy={geo.sy(hp[s.col])} r="4" fill={s.color} stroke="#fff" strokeWidth="2" />
              ))}
            </g>
          )}
        </svg>
        {hp && (
          <div className={"chart-tooltip" + (geo.sx(geo.xs[hover]) > W * 0.6 ? " is-flipped" : "")}
            style={{ left: `${(geo.sx(geo.xs[hover]) / W) * 100}%` }}>
            <strong>{fmtTime(hp.valid_time)}</strong>
            <span className="chart-tooltip__sub">issued {fmtTime(hp.timestamp)} · regime {hp.weather_regime}</span>
            {SERIES.map((s) => (
              <span key={s.col} className="chart-tooltip__row">
                <i style={{ background: s.color }} />{s.label}<b>{fmt(hp[s.col], meta.digits)}</b>
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="chart-legend">
        {SERIES.map((s) => (
          <span key={s.col}>
            <i className="legend-line" style={{ background: s.dash ? `repeating-linear-gradient(90deg, ${s.color} 0 5px, transparent 5px 9px)` : s.color, height: s.width }} />
            {s.label}
          </span>
        ))}
        <button type="button" className="link-button" onClick={() => setShowTable((v) => !v)}>
          {showTable ? "Hide table" : "Table view"}
        </button>
      </div>
      {showTable && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Valid time</th>{SERIES.map((s) => <th key={s.col}>{s.label}</th>)}</tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.valid_time}>
                  <td>{fmtTime(p.valid_time)}</td>
                  {SERIES.map((s) => <td key={s.col}>{fmt(p[s.col], meta.digits)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ForecastChart;
