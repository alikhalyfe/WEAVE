// Categorical slots validated with the dataviz palette checker (light surface):
// adjacent CVD ΔE ≥ 9.2, normal-vision ΔE ≥ 27.6. Aqua is < 3:1, so charts keep
// a legend + table view.
export const MODELS = [
  { key: "model_a", label: "Persistence", short: "Pers.", color: "#2a78d6" },
  { key: "model_b", label: "Random Forest", short: "RF", color: "#eb6834" },
  { key: "ai_model", label: "AI (Gradient Boosting)", short: "AI", color: "#1baf7a" },
];
export const BLEND = { key: "blended", label: "Adaptive blend", color: "#4a3aa7" };
export const OBSERVED = { key: "actual_value", label: "Observed (ERA5)", color: "#0f172a" };
export const MODEL_BY_KEY = Object.fromEntries(MODELS.map((m) => [m.key, m]));

// Live members (Open-Meteo). Validated order (dataviz checker, light surface):
// blue, orange, aqua, yellow, magenta, then violet for the blend -- worst
// adjacent CVD dE 9.1. Aqua/yellow/magenta are < 3:1 on white, so every chart
// keeps a legend + table view.
export const LIVE_MODELS = [
  { key: "ecmwf_ifs", label: "ECMWF IFS", short: "IFS", kind: "NWP", color: "#2a78d6", about: "ECMWF's flagship physics-based model" },
  { key: "gfs", label: "NCEP GFS", short: "GFS", kind: "NWP", color: "#eb6834", about: "NOAA's global physics-based model" },
  { key: "icon", label: "DWD ICON", short: "ICON", kind: "NWP", color: "#1baf7a", about: "Germany's global physics-based model" },
  { key: "aifs", label: "ECMWF AIFS", short: "AIFS", kind: "AI", color: "#eda100", about: "ECMWF's machine-learned forecast model" },
  { key: "ens", label: "ECMWF ENS mean", short: "ENS", kind: "Ensemble", color: "#e87ba4", about: "average of ECMWF's 51-member ensemble" },
];
export const LIVE_MODEL_BY_KEY = Object.fromEntries(LIVE_MODELS.map((m) => [m.key, m]));

export const VARIABLES = {
  precipitation_mm: { label: "Rainfall", unit: "mm/h", icon: "water_drop", accent: "blue", digits: 2, event: "Heavy rainfall" },
  temperature_2m_c: { label: "Temperature", unit: "°C", icon: "thermostat", accent: "amber", digits: 1, event: "Heat" },
  wind_speed_10m: { label: "Wind speed", unit: "m/s", icon: "air", accent: "teal", digits: 1, event: "High wind" },
};

export const REGIME_ICONS = { "Heavy Rain": "rainy", Heat: "sunny", "High Wind": "air", Normal: "partly_cloudy_day" };

export const LEVEL_LABELS = {
  location_season_hour: "Location · season · hour",
  location_hour: "Location · hour of day",
  location_season_regime: "Location · season · regime",
  location_season: "Location · season",
  location: "Location",
  global: "Global (variable + lead)",
  equal_weights: "Equal weights (no history)",
};

export const METHOD_LABELS = {
  equal: "Equal weights",
  inverse_mae: "Inverse MAE",
  inverse_mse: "Inverse MSE",
  optimal: "Optimal (NNLS stacking)",
  best_member: "Best single model",
};

export const CONFIG_LABELS = {
  regime: "Regime ladder",
  regime_bias: "Regime ladder + bias correction",
  diurnal_bias: "Diurnal + regime ladder + bias correction",
};
export const candidateLabel = (config, method) => `${METHOD_LABELS[method]} · ${CONFIG_LABELS[config]}`;

export const fmt = (v, digits = 1) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(digits));
export const pct = (v, digits = 0) => (v === null || v === undefined ? "—" : (v * 100).toFixed(digits) + "%");

// Timestamps come from the API as naive ISO strings; treat them as UTC
// wall-clock so the browser's timezone never shifts them.
export const toDate = (iso) => new Date(iso.slice(0, 19) + "Z");
export const toIso = (date) => date.toISOString().slice(0, 19);
export const addHours = (iso, h) => toIso(new Date(toDate(iso).getTime() + h * 3600e3));

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function fmtTime(iso, withYear = false) {
  if (!iso) return "—";
  const d = toDate(iso);
  const day = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}${withYear ? " " + d.getUTCFullYear() : ""}`;
  return `${day}, ${String(d.getUTCHours()).padStart(2, "0")}:00`;
}
export const fmtDay = (iso) => {
  const d = toDate(iso);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
};
export const MONTH_NAMES = MONTHS;

// Live pages show Indian Standard Time; the API speaks UTC.
const IST_MS = 5.5 * 3600e3;
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export function fmtIST(iso, { weekday = false, date = true } = {}) {
  if (!iso) return "—";
  const d = new Date(toDate(iso).getTime() + IST_MS);
  const hh = `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  if (!date) return hh;
  return `${weekday ? DAYS[d.getUTCDay()] + " " : ""}${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}, ${hh}`;
}
export const istHour = (iso) => new Date(toDate(iso).getTime() + IST_MS).getUTCHours();

/** "5 min ago" style age of a UTC ISO timestamp. */
export function ago(iso) {
  if (!iso) return "—";
  const mins = Math.round((Date.now() - toDate(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`;
}

export const severityOf = (p) => (p >= 0.66 ? "high" : p >= 0.33 ? "moderate" : "low");

/** "Thu 1 Oct" for an ISO date (YYYY-MM-DD). */
export const fmtDate = (d) => {
  const x = new Date(d + "T00:00:00Z");
  return `${DAYS[x.getUTCDay()]} ${x.getUTCDate()} ${MONTHS[x.getUTCMonth()]}`;
};

export const slug = (name) => name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
export const placeUrl = (p) => `/forecast?${new URLSearchParams({ name: p.name, lat: p.latitude.toFixed(4), lon: p.longitude.toFixed(4), ...(p.state ? { state: p.state } : {}) })}`;

// ---- Live units: wind is shown in km/h (API speaks m/s) ----
export const LIVE_VARIABLES = {
  precipitation_mm: { ...VARIABLES.precipitation_mm, unit: "mm", hourlyUnit: "mm/h", scale: 1, digits: 1 },
  temperature_2m_c: { ...VARIABLES.temperature_2m_c, unit: "°C", hourlyUnit: "°C", scale: 1, digits: 1 },
  wind_speed_10m: { ...VARIABLES.wind_speed_10m, unit: "km/h", hourlyUnit: "km/h", scale: 3.6, digits: 0 },
};
export const liveValue = (variable, v) => (v === null || v === undefined ? null : v * LIVE_VARIABLES[variable].scale);

// ---- Map colour scales (fixed, meaningful bins) ----
// Rainfall: IMD 24-hour categories on a single-hue blue ramp.
export const RAIN_BINS = [
  { min: 0, max: 0.1, label: "No rain", color: "#f1f5f9" },
  { min: 0.1, max: 2.5, label: "Very light", color: "#cde2fb" },
  { min: 2.5, max: 15.6, label: "Light", color: "#9ec5f4" },
  { min: 15.6, max: 64.5, label: "Moderate", color: "#5598e7" },
  { min: 64.5, max: 115.6, label: "Heavy", color: "#256abf" },
  { min: 115.6, max: 204.5, label: "Very heavy", color: "#184f95" },
  { min: 204.5, max: Infinity, label: "Extremely heavy", color: "#0d366b" },
];
// Daily max temperature: diverging blue <-> red around a grey 25-30 °C.
export const TEMP_BINS = [
  { min: -Infinity, max: 10, label: "< 10°", color: "#184f95" },
  { min: 10, max: 15, label: "10–15°", color: "#5598e7" },
  { min: 15, max: 20, label: "15–20°", color: "#9ec5f4" },
  { min: 20, max: 25, label: "20–25°", color: "#d7e6f7" },
  { min: 25, max: 30, label: "25–30°", color: "#f0efec" },
  { min: 30, max: 35, label: "30–35°", color: "#f6c6a8" },
  { min: 35, max: 40, label: "35–40°", color: "#ec8b63" },
  { min: 40, max: 45, label: "40–45°", color: "#d03b3b" },
  { min: 45, max: Infinity, label: "≥ 45°", color: "#8e1b1b" },
];
// Daily max wind (km/h): Beaufort bands, single-hue teal ramp.
export const WIND_BINS = [
  { min: 0, max: 12, label: "Light (< 12)", color: "#dff3ec" },
  { min: 12, max: 20, label: "Gentle", color: "#b3e3d2" },
  { min: 20, max: 29, label: "Moderate", color: "#7ccdb3" },
  { min: 29, max: 39, label: "Fresh", color: "#3fae8c" },
  { min: 39, max: 50, label: "Strong (≥ 39)", color: "#1b8566" },
  { min: 50, max: Infinity, label: "Near gale+", color: "#0b5d40" },
];
export const BINS = { precipitation_mm: RAIN_BINS, temperature_2m_c: TEMP_BINS, wind_speed_10m: WIND_BINS };
export const binFor = (variable, value) => (value === null || value === undefined ? null : BINS[variable].find((b) => value >= b.min && value < b.max));

export const HAZARD_ICON = { heat_wave: "local_fire_department", heavy_rain: "thunderstorm", high_wind: "air" };
export const LEVEL_STYLE = {
  warning: { label: "Warning", color: "#d03b3b" },
  watch: { label: "Watch", color: "#ec835a" },
  notice: { label: "Unusual", color: "#fab219" },
};
export const OFFICIAL_COLORS = { red: "#d03b3b", orange: "#ec835a", yellow: "#fab219", green: "#0ca30c" };
export const officialColor = (a) => OFFICIAL_COLORS[a.severity_color] || OFFICIAL_COLORS[(a.severity || "").toLowerCase()] || "#64748b";
