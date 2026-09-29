import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { fmt, toDate } from "../format";

const W = 800;
const PAD = { top: 14, right: 12, bottom: 26, left: 46 };

/** Decimals needed so neighbouring ticks never print the same label. */
function tickDecimals(ticks) {
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1;
  return Math.min(3, (String(+step.toFixed(6)).split(".")[1] || "").length);
}

function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const step = 10 ** Math.floor(Math.log10(span / count));
  const nice = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => span / s <= count) || step * 10;
  const ticks = [];
  for (let v = Math.ceil(min / nice) * nice; v <= max + 1e-9; v += nice) ticks.push(+v.toFixed(6));
  return ticks;
}

/**
 * Multi-series line chart over time with crosshair tooltip, legend and table view.
 * series: [{ key, label, color, width?, dash?, value: (point) => number|null }]
 * time: (point) => ISO string; fmtX: (iso) => tick label; fmtTip: (iso) => tooltip title
 * zero: y axis starts at 0; threshold: { value, label }; marker: { time, label }
 */
function TimeSeriesChart({ points, series, time, fmtX, fmtTip, digits = 1, zero = false, threshold, marker, height = 240, label, tipExtra }) {
  const [hover, setHover] = useState(null);
  const [table, setTable] = useState(false);
  const H = height;

  const geo = useMemo(() => {
    if (!points?.length) return null;
    const xs = points.map((p) => toDate(time(p)).getTime());
    const vals = points.flatMap((p) => series.map((s) => s.value(p))).filter((v) => v !== null && v !== undefined);
    if (threshold?.value != null) vals.push(threshold.value);
    if (!vals.length) return null;
    let lo = zero ? 0 : Math.min(...vals);
    let hi = Math.max(...vals);
    const pad = (hi - lo) * 0.08 || 1;
    hi += pad;
    if (!zero) lo -= pad;
    const [x0, x1] = [xs[0], xs[xs.length - 1]];
    const sx = (t) => PAD.left + ((t - x0) / (x1 - x0 || 1)) * (W - PAD.left - PAD.right);
    const sy = (v) => PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);
    const paths = series.map((s) => {
      let d = "";
      let pen = false;
      points.forEach((p, i) => {
        const v = s.value(p);
        if (v === null || v === undefined) return void (pen = false);
        d += `${pen ? "L" : "M"}${sx(xs[i]).toFixed(1)} ${sy(v).toFixed(1)}`;
        pen = true;
      });
      return { ...s, d };
    });
    const days = [];
    points.forEach((p, i) => {
      const label = fmtX(time(p));
      if (label) days.push({ x: sx(xs[i]), label });
    });
    const yTicks = niceTicks(lo, hi);
    return { xs, sx, sy, paths, yTicks, yDecimals: tickDecimals(yTicks), days };
  }, [points, series, time, fmtX, zero, threshold, H]);

  if (!geo) return <div className="chart-empty">No data for this selection.</div>;

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    let best = 0;
    geo.xs.forEach((t, i) => {
      if (Math.abs(geo.sx(t) - x) < Math.abs(geo.sx(geo.xs[best]) - x)) best = i;
    });
    setHover(best);
  };
  const hp = hover !== null ? points[hover] : null;
  const hx = hover !== null ? geo.sx(geo.xs[hover]) : 0;
  const markerX = marker ? geo.sx(toDate(marker.time).getTime()) : null;

  return (
    <div className="forecast-chart">
      <div className="forecast-chart__plot">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {geo.yTicks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={geo.sy(t)} y2={geo.sy(t)} className="chart-grid" />
              <text x={PAD.left - 8} y={geo.sy(t) + 3} className="chart-tick" textAnchor="end">{fmt(t, geo.yDecimals)}</text>
            </g>
          ))}
          {geo.days.map((t) => <text key={t.x} x={t.x} y={H - 8} className="chart-tick" textAnchor="middle">{t.label}</text>)}
          {threshold?.value != null && (
            <g>
              <line x1={PAD.left} x2={W - PAD.right} y1={geo.sy(threshold.value)} y2={geo.sy(threshold.value)} className="chart-threshold" />
              <text x={W - PAD.right - 4} y={geo.sy(threshold.value) - 4} textAnchor="end" className="chart-threshold-label">{threshold.label}</text>
            </g>
          )}
          {markerX !== null && markerX >= PAD.left && markerX <= W - PAD.right && (
            <g>
              <line x1={markerX} x2={markerX} y1={PAD.top} y2={H - PAD.bottom} className="chart-issue" />
              <text x={markerX + 4} y={PAD.top + 9} className="chart-issue-label">{marker.label}</text>
            </g>
          )}
          {geo.paths.map((p) => (
            <motion.path key={p.key + points.length} d={p.d} fill="none" stroke={p.color} strokeWidth={p.width || 1.6}
              strokeDasharray={p.dash} strokeLinejoin="round" strokeLinecap="round" opacity={p.faint ? 0.75 : 1}
              initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: p.faint ? 0.75 : 1 }}
              transition={{ duration: 0.9, ease: "easeOut" }} />
          ))}
          {hp && (
            <g>
              <line x1={hx} x2={hx} y1={PAD.top} y2={H - PAD.bottom} className="chart-crosshair" />
              {series.map((s) => {
                const v = s.value(hp);
                return v !== null && v !== undefined && <circle key={s.key} cx={hx} cy={geo.sy(v)} r="4" fill={s.color} stroke="#fff" strokeWidth="2" />;
              })}
            </g>
          )}
        </svg>
        {hp && (
          <div className={"chart-tooltip" + (hx > W * 0.6 ? " is-flipped" : "")} style={{ left: `${(hx / W) * 100}%` }}>
            <strong>{fmtTip(time(hp))}</strong>
            {tipExtra && <span className="chart-tooltip__sub">{tipExtra(hp)}</span>}
            {series.map((s) => (
              <span key={s.key} className="chart-tooltip__row"><i style={{ background: s.color }} />{s.label}<b>{fmt(s.value(hp), digits)}</b></span>
            ))}
          </div>
        )}
      </div>
      <div className="chart-legend">
        {series.map((s) => (
          <span key={s.key}>
            <i className="legend-line" style={{ background: s.dash ? `repeating-linear-gradient(90deg, ${s.color} 0 5px, transparent 5px 9px)` : s.color, height: s.width || 1.6 }} />
            {s.label}
          </span>
        ))}
        <button type="button" className="link-button" onClick={() => setTable((v) => !v)}>{table ? "Hide table" : "Table view"}</button>
      </div>
      {table && (
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Time</th>{series.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
            <tbody>
              {points.map((p) => (
                <tr key={time(p)}><td>{fmtTip(time(p))}</td>{series.map((s) => <td key={s.key}>{fmt(s.value(p), digits)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default TimeSeriesChart;
