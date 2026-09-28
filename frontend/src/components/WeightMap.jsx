import { useState } from "react";
import DashboardCard from "./DashboardCard";
import { MODELS, MODEL_BY_KEY, fmt, pct } from "../format";

// Approximate Maharashtra outline (lon, lat) -- context only, not a survey boundary.
const OUTLINE = [
  [72.8, 20.2], [73.0, 21.0], [74.0, 21.6], [74.8, 22.0], [76.0, 21.4], [77.2, 21.7], [78.3, 21.6], [79.2, 21.6],
  [80.0, 21.7], [80.6, 21.3], [80.9, 20.3], [80.4, 19.4], [80.0, 18.7], [79.2, 19.4], [78.3, 19.7], [77.8, 18.8],
  [77.5, 18.2], [77.6, 17.4], [76.6, 17.3], [75.6, 16.7], [74.5, 16.0], [74.0, 15.7], [73.4, 15.8], [73.3, 16.5],
  [73.1, 17.5], [72.9, 18.5], [72.8, 19.2],
];
const BOUNDS = { lon: [72.4, 81.2], lat: [15.4, 22.3] };
const MW = 520;
const MH = (MW * (BOUNDS.lat[1] - BOUNDS.lat[0])) / (BOUNDS.lon[1] - BOUNDS.lon[0]) / Math.cos((19 * Math.PI) / 180);
const px = (lon) => ((lon - BOUNDS.lon[0]) / (BOUNDS.lon[1] - BOUNDS.lon[0])) * MW;
const py = (lat) => ((BOUNDS.lat[1] - lat) / (BOUNDS.lat[1] - BOUNDS.lat[0])) * MH;

function arc(cx, cy, r, a0, a1) {
  const p = (a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a1);
  return `M${x0} ${y0} A${r} ${r} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1} ${y1}`;
}

function Donut({ row, x, y, selected, onSelect, digits }) {
  const gap = 0.06;
  const spans = MODELS.map((m) => row["weight_" + m.key] * Math.PI * 2);
  const starts = spans.map((_, i) => spans.slice(0, i).reduce((s, v) => s + v, 0));
  return (
    <g className={"map-city" + (selected ? " is-selected" : "")} onClick={() => onSelect(row.location)} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect(row.location)}>
      <title>{`${row.location}: ${MODELS.map((m) => `${m.label} ${pct(row["weight_" + m.key])}`).join(", ")}`}</title>
      <circle cx={x} cy={y} r="26" className="map-city__hit" />
      {MODELS.map((m, i) => spans[i] > gap * 2 && (
        <path key={m.key} d={arc(x, y, 18, starts[i] + gap / 2, starts[i] + spans[i] - gap / 2)} stroke={m.color} strokeWidth="7" fill="none" />
      ))}
      <text x={x} y={y + 3.5} textAnchor="middle" className="map-city__value">{fmt(row.blended, digits > 1 ? 1 : 0)}</text>
      <text x={x} y={y + 38} textAnchor="middle" className="map-label">{row.location.replace("Chhatrapati ", "Ch. ")}</text>
    </g>
  );
}

const TABS = [
  { key: "lead", label: "By lead time", table: "by_location_lead", col: "lead_time_hours", fmt: (v) => v + "h" },
  { key: "season", label: "By season", table: "by_location_season", col: "season" },
];

function WeightGrid({ weights, lead, tab }) {
  const rows = (weights?.[tab.table] || []).filter((r) => tab.key === "lead" || r.lead_time_hours === lead);
  const cols = [...new Set(rows.map((r) => r[tab.col]))];
  const locations = [...new Set(rows.map((r) => r.location))].sort();
  if (!rows.length) return null;
  return (
    <div className="table-scroll">
      <table className="weight-grid">
        <thead><tr><th />{cols.map((c) => <th key={c}>{tab.fmt ? tab.fmt(c) : c}</th>)}</tr></thead>
        <tbody>
          {locations.map((loc) => (
            <tr key={loc}>
              <th>{loc.replace("Chhatrapati ", "Ch. ")}</th>
              {cols.map((c) => {
                const r = rows.find((x) => x.location === loc && x[tab.col] === c);
                if (!r) return <td key={c} />;
                const m = MODEL_BY_KEY[r.dominant_model];
                const share = r[r.dominant_model];
                return (
                  <td key={c} title={MODELS.map((x) => `${x.label} ${pct(r[x.key])}`).join(" · ")}>
                    <span className="weight-grid__cell" style={{ "--c": m.color, "--a": Math.max(0.12, (share - 1 / 3) * 1.5) }}>
                      <i style={{ background: m.color }} />{m.short} {pct(share)}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WeightMap({ rows, locations, selected, onSelect, weights, lead, meta }) {
  const [tab, setTab] = useState(TABS[0]);
  const byLoc = Object.fromEntries((rows || []).map((r) => [r.location, r]));
  return (
    <DashboardCard
      id="weight-map"
      title="Model Weight Map"
      icon="map"
      subtitle={`Which model the blend trusts for ${meta.label.toLowerCase()} at each location`}
      className="map-card"
      action={<span className="card-tag">RING = WEIGHTS · CENTRE = BLEND {meta.unit.toUpperCase()}</span>}
    >
      <div className="weight-map">
        <svg viewBox={`0 0 ${MW} ${MH}`} role="img" aria-label="Map of Maharashtra showing model weights per location">
          <path d={"M" + OUTLINE.map(([lo, la]) => `${px(lo).toFixed(1)} ${py(la).toFixed(1)}`).join("L") + "Z"} className="map-outline" />
          <text x={px(72.55)} y={py(17.2)} className="map-caption" transform={`rotate(-72 ${px(72.55)} ${py(17.2)})`}>ARABIAN SEA</text>
          <text x={px(78.2)} y={py(16.4)} className="map-title">MAHARASHTRA</text>
          {(locations || []).map((l) => byLoc[l.location] && (
            <Donut key={l.location} row={byLoc[l.location]} x={px(l.longitude)} y={py(l.latitude)}
              selected={l.location === selected} onSelect={onSelect} digits={meta.digits} />
          ))}
        </svg>
        <div className="weight-map__legend">
          {MODELS.map((m) => <span key={m.key}><i style={{ background: m.color }} />{m.label}</span>)}
          <span className="muted">Click a city to select it</span>
        </div>
      </div>
      <div className="segmented" role="tablist">
        {TABS.map((t) => (
          <button type="button" key={t.key} role="tab" aria-selected={t.key === tab.key} className={t.key === tab.key ? "is-active" : ""} onClick={() => setTab(t)}>
            {t.label}
          </button>
        ))}
      </div>
      <p className="card-caption">Dominant model and its mean 2025 weight{tab.key === "season" ? ` at ${lead}h lead` : ""}.</p>
      <WeightGrid weights={weights} lead={lead} tab={tab} />
    </DashboardCard>
  );
}

export default WeightMap;
