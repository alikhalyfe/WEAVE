import DashboardCard from "../components/DashboardCard";
import ExtremeWeatherAlert from "../components/ExtremeWeatherAlert";
import ForecastCard from "../components/ForecastCard";
import Header from "../components/Header";
import ModelWeights from "../components/ModelWeights";
import RegionalMapPlaceholder from "../components/RegionalMapPlaceholder";
import Sidebar from "../components/Sidebar";
import WeatherRegime from "../components/WeatherRegime";

const modelWeights = [
  { name: "NWP Model 1", value: 25, color: "#6366f1" },
  { name: "NWP Model 2", value: 35, color: "#d97706" },
  { name: "AI Model", value: 40, color: "#0d9488" },
];

const performance = [
  { name: "NWP 1", value: 8.4, color: "#6366f1" },
  { name: "NWP 2", value: 7.1, color: "#d97706" },
  { name: "AI", value: 6.8, color: "#0d9488" },
  { name: "Blended", value: 5.9, color: "#0284c7" },
];

function Dashboard() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-column">
        <Header />
        <main className="dashboard-content" id="overview">
          <div className="page-intro">
            <div>
              <span className="eyebrow">OVERVIEW / ACTIVE FORECAST</span>
              <h2>Adaptive forecast blend</h2>
            </div>
            <span className="demo-label"><i /> Demonstration data</span>
          </div>

          <section className="forecast-grid" aria-label="Forecast summary">
            <ForecastCard label="Rainfall" value="82" unit="mm" detail="Expected accumulation" icon="water_drop" accent="blue" />
            <ForecastCard label="Temperature" value="27.4" unit="°C" detail="Surface temperature" icon="thermostat" accent="amber" />
            <ForecastCard label="Wind Speed" value="31" unit="km/h" detail="Sustained surface wind" icon="air" accent="teal" />
            <ForecastCard label="Weather Regime" value="Heavy Rain" unit="" detail="82% probability" icon="thunderstorm" accent="indigo" />
          </section>

          <div className="dashboard-grid">
            <div className="dashboard-grid__main">
              <DashboardCard
                id="forecast"
                title="Forecast Comparison"
                icon="show_chart"
                subtitle="Forecast model output over the selected lead time"
                className="forecast-comparison"
                action={<span className="card-tag">12 HOUR LEAD</span>}
              >
                <div className="chart-placeholder" role="img" aria-label="Forecast comparison chart placeholder">
                  <div className="chart-placeholder__y-labels"><span>80</span><span>60</span><span>40</span><span>20</span><span>0</span></div>
                  <svg viewBox="0 0 800 220" preserveAspectRatio="none" aria-hidden="true">
                    <path d="M0 18H800 M0 63H800 M0 108H800 M0 153H800 M0 198H800" className="chart-gridline" />
                    <path d="M0 159 C72 145 103 127 167 135 S280 109 335 115 S436 87 500 100 S618 63 670 74 S745 42 800 52" className="chart-line chart-line--one" />
                    <path d="M0 174 C73 159 119 148 167 143 S268 127 335 131 S440 110 500 115 S615 83 670 92 S737 68 800 70" className="chart-line chart-line--two" />
                    <path d="M0 166 C72 156 111 140 167 138 S272 117 335 121 S438 94 500 103 S612 73 670 80 S743 49 800 59" className="chart-line chart-line--three" />
                    <path d="M0 164 C70 151 110 137 167 139 S272 117 335 122 S438 96 500 105 S612 70 670 80 S743 51 800 60" className="chart-line chart-line--blend" />
                  </svg>
                  <div className="chart-placeholder__x-labels"><span>Now</span><span>+3h</span><span>+6h</span><span>+9h</span><span>+12h</span><span>+18h</span><span>+24h</span></div>
                </div>
                <div className="chart-legend">
                  <span><i className="legend-line legend-line--one" />NWP Model 1</span>
                  <span><i className="legend-line legend-line--two" />NWP Model 2</span>
                  <span><i className="legend-line legend-line--three" />AI Model</span>
                  <span><i className="legend-line legend-line--blend" />Blended Forecast</span>
                </div>
              </DashboardCard>

              <div className="dashboard-grid__lower">
                <DashboardCard
                  id="performance"
                  title="Model Performance"
                  icon="analytics"
                  subtitle="Mean absolute error · lower is better"
                  className="performance-card"
                  action={<span className="card-tag">MAE · MM</span>}
                >
                  <div className="performance-list">
                    {performance.map((model) => (
                      <div className="performance-row" key={model.name}>
                        <span className="performance-row__name"><i style={{ background: model.color }} />{model.name}</span>
                        <div className="performance-row__track"><span style={{ width: (model.value / 10 * 100) + "%", background: model.color }} /></div>
                        <strong>{model.value.toFixed(1)}</strong>
                      </div>
                    ))}
                  </div>
                  <div className="performance-note"><span className="material-symbols-outlined" aria-hidden="true">auto_awesome</span> Blended forecast has the lowest error.</div>
                </DashboardCard>

                <DashboardCard
                  title="Regional Forecast Map"
                  icon="map"
                  subtitle="Illustrative rainfall overlay"
                  className="map-card"
                  action={<span className="card-tag">MAP PREVIEW</span>}
                >
                  <RegionalMapPlaceholder />
                </DashboardCard>
              </div>
            </div>

            <aside className="dashboard-grid__side">
              <ModelWeights weights={modelWeights} />
              <WeatherRegime />
              <ExtremeWeatherAlert />
            </aside>
          </div>

          <footer className="dashboard-footer">
            <span><i /> AWFB adaptive weather forecast blending</span>
            <span>Static demonstration values · Prototype dashboard</span>
          </footer>
        </main>
      </div>
    </div>
  );
}

export default Dashboard;
