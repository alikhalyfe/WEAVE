const links = [
  { label: "Overview", icon: "grid_view", href: "#overview" },
  { label: "Forecast", icon: "trending_up", href: "#forecast" },
  { label: "Model Weights", icon: "tune", href: "#weights" },
  { label: "Weight Map", icon: "map", href: "#weight-map" },
  { label: "Performance", icon: "analytics", href: "#performance" },
  { label: "Extreme Events", icon: "warning", href: "#extreme-events" },
  { label: "Blend New Data", icon: "bolt", href: "#live-blend" },
  { label: "Workflow", icon: "settings_suggest", href: "#workflow" },
];

function Sidebar({ status }) {
  return (
    <aside className="sidebar">
      <div>
        <a className="brand" href="#overview" aria-label="WEAVE dashboard overview">
          <span className="brand__mark">W</span>
          <span className="brand__copy">
            <strong>WEAVE</strong>
            <span>Adaptive Weather<br />Forecast Blending</span>
          </span>
        </a>

        <div className="sidebar__label">Workspace</div>
        <nav className="sidebar__nav" aria-label="Main navigation">
          {links.map((link) => (
            <a href={link.href} className="sidebar__link" key={link.label}>
              <span className="material-symbols-outlined" aria-hidden="true">{link.icon}</span>
              <span>{link.label}</span>
            </a>
          ))}
        </nav>
      </div>

      <div className="sidebar__footer">
        <span className={"online-dot" + (status === "online" ? "" : " is-off")} />
        <span>{status === "online" ? "Live data" : "No data"}</span>
        <span className="sidebar__footer-tag">ERA5 · 2025</span>
      </div>
    </aside>
  );
}

export default Sidebar;
