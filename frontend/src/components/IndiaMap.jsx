import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useEffect } from "react";

const INDIA_BOUNDS = [[6.5, 68.0], [35.8, 97.4]];

function FitTo({ focus }) {
  const map = useMap();
  useEffect(() => {
    if (focus) map.flyTo([focus.latitude, focus.longitude], Math.max(map.getZoom(), 7), { duration: 0.8 });
  }, [focus, map]);
  return null;
}

/**
 * India basemap (OpenStreetMap standard tiles, desaturated in CSS) with one circle per point.
 * points: [{ id, latitude, longitude, color, radius?, ring?, label, detail?, onClick? }]
 */
function IndiaMap({ points, height = 420, focus, legend, ariaLabel = "Map of India" }) {
  return (
    <div className="india-map" style={{ height }} role="region" aria-label={ariaLabel}>
      <MapContainer bounds={focus ? undefined : INDIA_BOUNDS} center={focus ? [focus.latitude, focus.longitude] : undefined}
        zoom={focus ? 8 : undefined} scrollWheelZoom={false} className="india-map__canvas" attributionControl>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={12} className="india-map__tiles" />
        {focus && <FitTo focus={focus} />}
        {points.map((p) => (
          <CircleMarker key={p.id} center={[p.latitude, p.longitude]} radius={p.radius || 8}
            pathOptions={{ color: p.ring || "#ffffff", weight: p.ring ? 3 : 2, fillColor: p.color, fillOpacity: 0.9 }}
            eventHandlers={p.onClick ? { click: p.onClick } : undefined}>
            <Tooltip direction="top" offset={[0, -6]}>
              <strong>{p.label}</strong>
              {p.detail && <><br />{p.detail}</>}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
      {legend && <div className="india-map__legend">{legend}</div>}
    </div>
  );
}

export default IndiaMap;
