import DashboardCard from "./DashboardCard";

function WeatherRegime() {
  return (
    <DashboardCard title="Weather Regime" icon="thunderstorm" className="regime-card">
      <div className="regime-card__content">
        <span className="regime-card__weather-icon material-symbols-outlined" aria-hidden="true">rainy</span>
        <div>
          <strong>Heavy Rain</strong>
          <span>Monsoon conditions</span>
        </div>
        <div className="regime-card__probability">
          <strong>82%</strong>
          <span>Probability</span>
        </div>
      </div>
      <div className="probability-track"><span style={{ width: "82%" }} /></div>
    </DashboardCard>
  );
}

export default WeatherRegime;
