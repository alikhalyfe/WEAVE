import "leaflet/dist/leaflet.css";
import { CircleMarker, GeoJSON, MapContainer, Rectangle, TileLayer, Tooltip } from "react-leaflet";
import { BINS, LIVE_MODEL_BY_KEY, LIVE_VARIABLES, binFor, fmt, liveValue, officialColor, pct } from "../format";

const INDIA_BOUNDS = [[6.5, 68.0], [35.8, 97.4]];
const boundaryStyle = { color: "#334155", weight: 1.2, fill: false, dashArray: null };

function cellValue(cell, variable, day) {
  return liveValue(variable, cell.values[variable]?.[day]);
}

/**
 * The live India map.
 * layer: "forecast" (blended daily field) | "model" (most-trusted model by region)
 * grid: /api/live/grid payload; boundary: GeoJSON; cities: tracked-city items;
 * official: SACHET alerts; day: index into grid.dates.
 */
function IndiaGridMap({ grid, boundary, variable, day, layer, cities = [], official = [], showOfficial = true, onCity, height = 480 }) {
  const step = grid?.step_deg || 1.5;
  const half = step / 2;
  const meta = LIVE_VARIABLES[variable];

  return (
    <div className="india-map" style={{ height }}>
      <MapContainer bounds={INDIA_BOUNDS} scrollWheelZoom={false} className="india-map__canvas" zoomSnap={0.25}>
        <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={10} className="india-map__tiles"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
        {(grid?.cells || []).map((c) => {
          const bounds = [[c.lat - half, c.lon - half], [c.lat + half, c.lon + half]];
          if (layer === "model") {
            const key = c.dominant[variable]?.[day];
            const w = c.weights?.[variable]?.[String(Math.min(day, 7))]?.[key];
            const m = LIVE_MODEL_BY_KEY[key];
            if (!m) return null;
            return (
              <Rectangle key={`${c.lat},${c.lon}`} bounds={bounds} pathOptions={{ stroke: false, fillColor: m.color, fillOpacity: 0.25 + 0.55 * (w ?? 0.3) }}>
                <Tooltip sticky>
                  <strong>{m.label}</strong> leads here ({pct(w)})<br />
                  Weights from {c.neighbours.join(", ")}
                </Tooltip>
              </Rectangle>
            );
          }
          const v = cellValue(c, variable, day);
          const bin = binFor(variable, v);
          if (!bin) return null;
          return (
            <Rectangle key={`${c.lat},${c.lon}`} bounds={bounds} pathOptions={{ stroke: false, fillColor: bin.color, fillOpacity: 0.72 }}>
              <Tooltip sticky>
                <strong>{fmt(v, meta.digits)} {meta.unit}</strong> · {bin.label}
                {variable === "temperature_2m_c" && c.values.temperature_min?.[day] != null && <> · low {fmt(c.values.temperature_min[day], 0)}°C</>}
                <br />{c.lat.toFixed(1)}°N {c.lon.toFixed(1)}°E · weights from {c.neighbours.join(", ") || "equal (no verified city yet)"}
              </Tooltip>
            </Rectangle>
          );
        })}
        {boundary && <GeoJSON data={boundary} style={boundaryStyle} interactive={false} />}
        {cities.filter((c) => c.place).map((c) => {
          const alert = c.summary?.alerts?.find((a) => a.level !== "notice");
          return (
            <CircleMarker key={c.label} center={[c.place.latitude, c.place.longitude]} radius={c.status === "ready" ? 5 : 3.5}
              pathOptions={{ color: alert ? "#d03b3b" : "#0f172a", weight: alert ? 3 : 1.5, fillColor: "#ffffff", fillOpacity: 1 }}
              eventHandlers={onCity && c.status === "ready" ? { click: () => onCity(c) } : undefined}>
              <Tooltip direction="top" offset={[0, -4]}>
                <strong>{c.name}</strong>
                {c.summary?.outlook?.[0] && <><br />Today: {c.summary.outlook[0].headline}, {fmt(c.summary.outlook[0].high, 0)}° / {fmt(c.summary.outlook[0].low, 0)}°</>}
                {alert && <><br />⚠ {alert.label} ({alert.day_label})</>}
                {c.status !== "ready" && <><br />Learning model skill…</>}
              </Tooltip>
            </CircleMarker>
          );
        })}
        {showOfficial && official.filter((a) => a.latitude != null).map((a) => (
          <CircleMarker key={a.id} center={[a.latitude, a.longitude]} radius={7}
            pathOptions={{ color: officialColor(a), weight: 2.5, fillColor: officialColor(a), fillOpacity: 0.25, dashArray: "3 3" }}>
            <Tooltip direction="top">
              <strong>{a.type}</strong> · {a.severity} ({a.source})<br />{a.area}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
      <div className="india-map__legend">
        {layer === "model" ? (
          ["ecmwf_ifs", "gfs", "icon", "aifs", "ens"].map((k) => (
            <span key={k}><i style={{ background: LIVE_MODEL_BY_KEY[k].color }} />{LIVE_MODEL_BY_KEY[k].short}</span>
          ))
        ) : (
          BINS[variable].map((b) => <span key={b.label}><i className="sq" style={{ background: b.color }} />{b.label}</span>)
        )}
        <span><i className="ring" />city with warning</span>
        {showOfficial && <span><i className="dashed" />official alert</span>}
      </div>
    </div>
  );
}

export default IndiaGridMap;
