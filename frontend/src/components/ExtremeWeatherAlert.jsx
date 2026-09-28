import DashboardCard from "./DashboardCard";

function ExtremeWeatherAlert() {
  return (
    <DashboardCard title="Extreme Weather Alert" icon="warning" className="alert-card">
      <div className="alert-card__headline">
        <span className="alert-card__severity">HIGH SEVERITY</span>
        <span className="alert-card__probability">82% probability</span>
      </div>
      <h3>Heavy Rain Expected</h3>
      <p>Heavy rainfall is likely across the selected region during the forecast period.</p>
      <div className="alert-card__rainfall">
        <span className="material-symbols-outlined" aria-hidden="true">water_drop</span>
        <span>Expected rainfall</span>
        <strong>75–95 mm</strong>
      </div>
    </DashboardCard>
  );
}

export default ExtremeWeatherAlert;
