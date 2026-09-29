import { AnimatePresence, MotionConfig } from "motion/react";
import { Suspense, lazy } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { SkeletonCard } from "./components/Motion";
import Sidebar from "./components/Sidebar";

// One chunk per page: the map library only loads on pages that draw maps.
const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const ForecastPage = lazy(() => import("./pages/ForecastPage"));
const WeightsPage = lazy(() => import("./pages/WeightsPage"));
const PerformancePage = lazy(() => import("./pages/PerformancePage"));
const ExtremesPage = lazy(() => import("./pages/ExtremesPage"));
const BlendPage = lazy(() => import("./pages/BlendPage"));
const HistoricalPage = lazy(() => import("./pages/HistoricalPage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));
const OperationsPage = lazy(() => import("./pages/OperationsPage"));
import "./App.css";
import "./dashboard.css";
import "./pages.css";
import "./polish.css";

function NotFound() {
  return <main className="dashboard-content"><div className="chart-empty">Page not found.</div></main>;
}

function App() {
  const location = useLocation();
  return (
    <MotionConfig reducedMotion="user">
      <div className="app-shell">
        <Sidebar />
        <div className="main-column">
          <AnimatePresence mode="wait">
            <div key={location.pathname} className="route">
              <Suspense fallback={<main className="dashboard-content"><SkeletonCard lines={3} height={300} /></main>}>
              <Routes location={location}>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/forecast" element={<ForecastPage />} />
                <Route path="/weights" element={<WeightsPage />} />
                <Route path="/performance" element={<PerformancePage />} />
                <Route path="/extremes" element={<ExtremesPage />} />
                <Route path="/blend" element={<BlendPage />} />
                <Route path="/historical" element={<HistoricalPage />} />
                <Route path="/about" element={<AboutPage />} />
                <Route path="/operations" element={<OperationsPage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
              </Suspense>
            </div>
          </AnimatePresence>
          <footer className="dashboard-footer site-footer">
            <span><i /> WEAVE · adaptive AI–NWP forecast blending</span>
            <span>Weather data by Open-Meteo.com (CC BY 4.0): ECMWF, NOAA NCEP, DWD · ERA5 © Copernicus C3S · official warnings: NDMA SACHET · boundary: Survey of India via datameet (CC-0) · map © OpenStreetMap contributors</span>
          </footer>
        </div>
      </div>
    </MotionConfig>
  );
}

export default App;
