import { Rise, Stagger } from "./Motion";
import { LIVE_VARIABLES, fmt, pct } from "../format";

const AGG_LABEL = { temperature_2m_c: "daily max", precipitation_mm: "daily total", wind_speed_10m: "daily max" };
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** One tile per IST day: blended daily value, the ensemble's 10-90% range,
 * and how it compares with the unusual-for-the-date threshold. Values in
 * `days` are already in display units; ensemble stats are scaled here. */
function DailyOutlook({ days, variable, digits }) {
  const { unit, scale } = LIVE_VARIABLES[variable];
  return (
    <Stagger className="daily-outlook">
      {days.map((d) => {
        const date = new Date(d.date + "T00:00:00Z");
        const ratio = d.threshold ? Math.min(1, (d.blended ?? 0) / d.threshold) : 0;
        const e = d.ensemble;
        return (
          <Rise key={d.date} className={"day-tile" + (d.event ? " is-event" : "")}>
            <span className="day-tile__date">{WEEKDAY[date.getUTCDay()]} {date.getUTCDate()} {MONTH[date.getUTCMonth()]}</span>
            <strong>{fmt(d.blended, digits)}<small> {unit}</small></strong>
            {e && <span className="day-tile__range" title="10th to 90th percentile of the 51 ECMWF ensemble members">range {fmt(e.p10 * scale, digits)}–{fmt(e.p90 * scale, digits)}</span>}
            <span className="day-tile__meter" aria-hidden="true"><i style={{ width: ratio * 100 + "%" }} /></span>
            <span className="day-tile__thr">{AGG_LABEL[variable]} · unusual ≥ {fmt(d.threshold, digits)}</span>
            {d.event ? (
              <span className="day-tile__flag"><span className="material-symbols-outlined" aria-hidden="true">insights</span>Unusual · {pct(d.probability)} agree</span>
            ) : e?.above_local_p95 != null ? (
              <span className="day-tile__ok">{pct(e.above_local_p95)} of ensemble unusual</span>
            ) : null}
            {!d.complete && <span className="day-tile__partial">from {d.first_hour_ist} IST ({d.hours} h)</span>}
          </Rise>
        );
      })}
    </Stagger>
  );
}

export default DailyOutlook;
