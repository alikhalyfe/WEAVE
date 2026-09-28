import { useState } from "react";
import { MONTH_NAMES, fmt, fmtDay, toDate } from "../format";

const W = 800;
const H = 70;

/** Daily blended values for the whole evaluation year; click a day to jump there. */
function YearTimeline({ daily, issueTime, onPick, meta }) {
  const [hover, setHover] = useState(null);
  const days = daily?.days || [];
  if (!days.length) return null;
  const max = Math.max(...days.map((d) => Math.max(d.blended ?? 0, d.actual ?? 0)), 1e-9);
  const min = meta.label === "Temperature" ? Math.min(...days.map((d) => d.blended ?? max)) - 1 : 0;
  const bw = W / days.length;
  const selected = issueTime.slice(0, 10);
  // Rainfall is heavily skewed: a square-root scale keeps ordinary wet days visible.
  const f = meta.label === "Rainfall" ? Math.sqrt : (v) => v;
  const h = (v) => ((f(v) - f(min)) / (f(max) - f(min))) * (H - 14);

  return (
    <div className="timeline">
      <svg viewBox={`0 0 ${W} ${H + 14}`} role="img" aria-label={`Daily ${meta.label} blend for the year; click to select a day`}
        onMouseLeave={() => setHover(null)}>
        {days.map((d, i) => {
          const isSel = d.date.slice(0, 10) === selected;
          return (
            <g key={d.date} onMouseEnter={() => setHover(i)} onClick={() => onPick(d.date.slice(0, 10))} className="timeline__day">
              <rect x={i * bw} y={0} width={bw} height={H} fill="transparent" />
              <rect x={i * bw + 0.3} y={H - h(d.blended ?? min)} width={Math.max(bw - 0.6, 0.8)} height={h(d.blended ?? min)}
                className={isSel ? "timeline__bar is-selected" : "timeline__bar"} />
              {d.guidance_events > 0 && <rect x={i * bw} y={0} width={Math.max(bw, 1.2)} height={4} className="timeline__event" />}
            </g>
          );
        })}
        {MONTH_NAMES.map((m, k) => {
          const i = days.findIndex((d) => toDate(d.date).getUTCMonth() === k);
          return i >= 0 && <text key={m} x={i * bw + 2} y={H + 12} className="chart-tick">{m}</text>;
        })}
      </svg>
      <div className="timeline__caption">
        {hover !== null ? (
          <span>
            <strong>{fmtDay(days[hover].date)}</strong> · daily {daily.aggregation} blend {fmt(days[hover].blended, meta.digits)} / observed{" "}
            {fmt(days[hover].actual, meta.digits)} {meta.unit}
            {days[hover].guidance_events > 0 && ` · ${days[hover].guidance_events}h with extreme guidance`}
          </span>
        ) : (
          <span>Daily {daily.aggregation} of the blended forecast · <i className="timeline__key" /> extreme guidance issued · click any day</span>
        )}
      </div>
    </div>
  );
}

export default YearTimeline;
