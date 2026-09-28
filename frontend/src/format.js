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
