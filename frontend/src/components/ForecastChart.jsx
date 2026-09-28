import TimeSeriesChart from "./TimeSeriesChart";
import { BLEND, MODELS, OBSERVED, addHours, fmtTime } from "../format";

const SERIES = [
  ...MODELS.map((m) => ({ key: m.key, label: m.label, color: m.color, faint: true, value: (p) => p[m.key + "_forecast"] })),
  { key: "blended", label: BLEND.label, color: BLEND.color, width: 3, value: (p) => p.blended },
  { key: "actual", label: OBSERVED.label, color: OBSERVED.color, dash: "5 4", value: (p) => p.actual_value },
];
const midnight = (iso) => (iso.slice(11, 13) === "00" ? fmtTime(iso).split(",")[0] : null);

/** Historical replay: members, blend and ERA5 by valid time around an issue time. */
function ForecastChart({ points, issueTime, variable, meta, lead }) {
  return (
    <TimeSeriesChart points={points} series={SERIES} time={(p) => p.valid_time} fmtX={midnight} fmtTip={fmtTime}
      digits={meta.digits} zero={variable !== "temperature_2m_c"} label={`${meta.label} forecasts by model, blend and observation`}
      marker={{ time: addHours(issueTime, lead), label: `valid at selected issue +${lead}h` }}
      tipExtra={(p) => `issued ${fmtTime(p.timestamp)} · regime ${p.weather_regime}`} />
  );
}

export default ForecastChart;
