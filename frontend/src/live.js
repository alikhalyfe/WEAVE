import { useEffect, useState } from "react";
import { api, qs, useApi } from "./api";

/** Tracked-city overview; keeps polling while cities are still computing. */
export function useCities() {
  return useApi("/live/cities", { pollMs: 4000, poll: (d) => d.ready < d.total });
}

export function useLiveForecast(place) {
  const res = useApi(place ? "/live/forecast" + qs({ name: place.name, lat: place.latitude, lon: place.longitude, state: place.state }) : null);
  const [relay, setRelay] = useState({ key: null, data: null, error: null });
  const key = place ? `${place.latitude},${place.longitude}` : null;
  const needRelay = Boolean(res.error?.relay) && key !== null;
  useEffect(() => {
    if (!needRelay) return;
    let live = true;
    setRelay({ key, data: null, error: null });
    relayForecast(place)
      .then((data) => live && setRelay({ key, data, error: null }))
      .catch((error) => live && setRelay({ key, data: null, error }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- place is identified by key
  }, [needRelay, key]);
  if (!needRelay) return res;
  const mine = relay.key === key;
  return { data: mine ? relay.data : null, error: mine ? relay.error : null, loading: !mine || (!relay.data && !relay.error), relaying: true };
}

// Fallback only (the API answered 503 with relay: true): this browser fetches
// the exact Open-Meteo URLs the server lists and posts the JSON back for
// blending. Only https *.open-meteo.com URLs are fetched, without cookies or
// referrer; the server shape-checks everything and stores none of it.
const OPEN_METEO = /^(api|previous-runs-api|archive-api|ensemble-api)\.open-meteo\.com$/;
const RELAY_ROUNDS = 4;

function openMeteoUrl(u) {
  try {
    const url = new URL(u);
    return url.protocol === "https:" && OPEN_METEO.test(url.hostname) && !url.username && !url.password && !url.port;
  } catch {
    return false;
  }
}

async function relayForecast(place) {
  const responses = {};
  for (let round = 0; round <= RELAY_ROUNDS; round++) {
    const body = await api("/live/forecast/relay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: place.name, lat: place.latitude, lon: place.longitude, state: place.state, responses }),
    });
    if (!body.needs) return body;
    await Promise.all(body.needs.slice(0, 20).map(async (u) => {
      if (!openMeteoUrl(u)) return void (responses[u] = null);
      try {
        const r = await fetch(u, { credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store" });
        responses[u] = r.ok ? await r.json() : null;
      } catch {
        responses[u] = null;
      }
    }));
  }
  throw new Error("Open-Meteo could not be reached from this browser either.");
}

/** Place from the URL query (?name&lat&lon&state), or null. */
export function placeFromSearch(search) {
  const p = new URLSearchParams(search);
  const lat = Number(p.get("lat"));
  const lon = Number(p.get("lon"));
  if (!p.get("name") || !Number.isFinite(lat) || !Number.isFinite(lon) || !p.get("lat")) return null;
  return { name: p.get("name"), state: p.get("state") || null, latitude: lat, longitude: lon };
}

// Sequential single-hue ramp (dataviz reference blue, light -> dark).
const RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"];

/** Quantile bins over the values actually present, so colours encode rank
 * among the cities shown; the legend prints each bin's real range. */
export function binScale(values) {
  const v = values.filter((x) => x !== null && x !== undefined).sort((a, b) => a - b);
  if (!v.length) return { color: () => "#cbd5e1", bins: [] };
  const q = (f) => v[Math.min(v.length - 1, Math.round(f * (v.length - 1)))];
  // Quantile edges, de-duplicated so skewed data (many zero-rain cities) never shows empty or repeated bins.
  const edges = [...new Set(Array.from({ length: RAMP.length + 1 }, (_, i) => q(i / RAMP.length)))];
  const n = Math.max(1, edges.length - 1);
  const ramp = Array.from({ length: n }, (_, i) => RAMP[n === 1 ? 3 : Math.round((i * (RAMP.length - 1)) / (n - 1))]);
  const color = (x) => {
    if (x === null || x === undefined) return "#cbd5e1";
    const i = edges.slice(1).findIndex((e) => x <= e);
    return ramp[i < 0 ? n - 1 : Math.min(i, n - 1)];
  };
  const bins = edges.length === 1 ? [{ color: ramp[0], from: edges[0], to: edges[0] }]
    : ramp.map((c, i) => ({ color: c, from: edges[i], to: edges[i + 1] }));
  return { color, bins };
}

export const SUMMARY_LABELS = {
  temperature_2m_c: "max temperature, next 24 h",
  precipitation_mm: "total rainfall, next 24 h",
  wind_speed_10m: "max wind, next 24 h",
};
export const SUMMARY_UNITS = { temperature_2m_c: "°C", precipitation_mm: "mm", wind_speed_10m: "m/s" };
