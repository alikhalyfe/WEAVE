import DashboardCard from "./DashboardCard";
import { REGIME_ICONS, fmtTime } from "../format";

const DESCRIPTIONS = {
  "Heavy Rain": "Rain at or above the local p95 for this season",
  Heat: "Temperature at or above the local p95 for this season",
  "High Wind": "Wind at or above the local p95 for this season",
  Normal: "No variable above its local p95 threshold",
};

function WeatherRegime({ row, issueTime }) {
  if (!row) return null;
  const regime = row.weather_regime;
  return (
    <DashboardCard title="Weather Regime" icon="thunderstorm" className="regime-card"
      subtitle={`${row.location} · issue time ${fmtTime(issueTime)}`}>
      <div className="regime-card__content">
        <span className="regime-card__weather-icon material-symbols-outlined" aria-hidden="true">{REGIME_ICONS[regime]}</span>
        <div>
          <strong>{regime}</strong>
          <span>{row.season} · {DESCRIPTIONS[regime]}</span>
        </div>
      </div>
      <p className="card-caption">The regime selects which historical skill record the blend weights are learned from.</p>
    </DashboardCard>
  );
}

export default WeatherRegime;
