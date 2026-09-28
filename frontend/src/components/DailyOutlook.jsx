import { Rise, Stagger } from "./Motion";
import { fmt, pct, severityOf } from "../format";

const AGG_LABEL = { temperature_2m_c: "max", precipitation_mm: "total", wind_speed_10m: "max" };
const UNIT = { temperature_2m_c: "°C", precipitation_mm: "mm", wind_speed_10m: "m/s" };
const WEEKDAY = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** One tile per IST day: blended daily aggregate vs that day's p95 threshold. */
function DailyOutlook({ days, variable, digits }) {
  return (
    <Stagger className="daily-outlook">
      {days.map((d) => {
        const date = new Date(d.date + "T00:00:00Z");
        const ratio = d.threshold ? Math.min(1, (d.blended ?? 0) / d.threshold) : 0;
        return (
          <Rise key={d.date} className={"day-tile" + (d.event ? " is-event is-" + severityOf(d.probability ?? 0) : "")}>
            <span className="day-tile__date">{WEEKDAY[date.getUTCDay()]} {date.getUTCDate()} {MONTH[date.getUTCMonth()]}</span>
            <strong>{fmt(d.blended, digits)}<small> {UNIT[variable]}</small></strong>
            <span className="day-tile__meter" aria-hidden="true"><i style={{ width: ratio * 100 + "%" }} /></span>
            <span className="day-tile__thr">p95 {fmt(d.threshold, digits)} · {AGG_LABEL[variable]}</span>
            {d.event ? (
              <span className="day-tile__flag"><span className="material-symbols-outlined" aria-hidden="true">warning</span>{pct(d.probability)} agree</span>
            ) : (
              <span className="day-tile__ok">{pct(d.probability)} of models reach p95</span>
            )}
            {!d.complete && <span className="day-tile__partial">from {d.first_hour_ist} IST ({d.hours} h)</span>}
          </Rise>
        );
      })}
    </Stagger>
  );
}

export default DailyOutlook;
