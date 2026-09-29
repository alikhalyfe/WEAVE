import { motion } from "motion/react";
import { useState } from "react";
import { HAZARD_ICON, LEVEL_STYLE, fmt } from "../format";

function RainChance({ value }) {
  if (value === null || value === undefined) return null;
  return (
    <span className="rain-chance" title="Share of the 51 ECMWF ensemble forecasts with at least 1 mm of rain">
      <span className="material-symbols-outlined" aria-hidden="true">water_drop</span>
      {Math.round(value * 100)}%
    </span>
  );
}

/** The week in plain language, generated from the blended numbers. */
function WeekOutlook({ outlook, place }) {
  const [open, setOpen] = useState(0);
  if (!outlook?.length) return null;
  const temps = outlook.flatMap((d) => [d.low, d.high]).filter((x) => x != null);
  const lo = Math.min(...temps);
  const hi = Math.max(...temps);
  const pos = (t) => ((t - lo) / (hi - lo || 1)) * 100;

  return (
    <div className="week">
      <p className="week__lead">
        <span className="material-symbols-outlined" aria-hidden="true">{outlook[0].icon}</span>
        <span><strong>{place}, {outlook[0].label.toLowerCase()}:</strong> {outlook[0].text}</span>
      </p>
      <ul className="week__list">
        {outlook.map((d, i) => {
          const hazards = d.hazards.filter((h) => h.level !== "notice");
          const expanded = open === i;
          return (
            <li key={d.date} className={"week__row" + (expanded ? " is-open" : "")}>
              <button type="button" className="week__summary" onClick={() => setOpen(expanded ? -1 : i)} aria-expanded={expanded}>
                <span className="week__day">{d.label}{!d.complete && i === 0 && <small> from {d.first_hour_ist}</small>}</span>
                <span className="material-symbols-outlined week__icon" aria-hidden="true">{d.icon}</span>
                <span className="week__headline">
                  {d.headline}
                  {hazards.map((h) => (
                    <span key={h.type} className="hazard-chip" style={{ "--c": LEVEL_STYLE[h.level].color }}>
                      <span className="material-symbols-outlined" aria-hidden="true">{HAZARD_ICON[h.type]}</span>{h.label}
                    </span>
                  ))}
                </span>
                <RainChance value={d.rain_chance} />
                <span className="week__temps" aria-label={`Low ${fmt(d.low, 0)}, high ${fmt(d.high, 0)} degrees`}>
                  <span className="week__lo">{fmt(d.low, 0)}°</span>
                  <span className="week__bar"><i style={{ left: pos(d.low ?? lo) + "%", right: 100 - pos(d.high ?? hi) + "%" }} /></span>
                  <span className="week__hi">{fmt(d.high, 0)}°</span>
                </span>
              </button>
              {expanded && (
                <motion.div className="week__detail" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} transition={{ duration: 0.25 }}>
                  <p>{d.text}</p>
                  {d.hazards.filter((h) => h.level === "notice").map((h) => <p key={h.type} className="muted">{h.sentence}</p>)}
                  <dl className="week__facts">
                    <div><dt>Rain</dt><dd>{fmt(d.rain_mm, 1)} mm{d.rain_range?.[1] != null && ` (ensemble 10–90%: ${fmt(d.rain_range[0], 0)}–${fmt(d.rain_range[1], 0)} mm)`}</dd></div>
                    <div><dt>Wind</dt><dd>up to {fmt(d.wind_kmh, 0)} km/h</dd></div>
                    {d.normal_high != null && <div><dt>Normal high</dt><dd>{fmt(d.normal_high, 0)}°C</dd></div>}
                    {d.cloud != null && <div><dt>Daytime cloud</dt><dd>{fmt(d.cloud, 0)}%</dd></div>}
                  </dl>
                </motion.div>
              )}
            </li>
          );
        })}
      </ul>
      <p className="card-caption">
        Written automatically from WEAVE’s blended forecast. Rain chance = share of the 51 ECMWF ensemble members with ≥ 1 mm.
        Warnings follow IMD rainfall categories and heat-wave criteria; “normal” is the ERA5 average for the date over the last 2 years.
      </p>
    </div>
  );
}

export default WeekOutlook;
