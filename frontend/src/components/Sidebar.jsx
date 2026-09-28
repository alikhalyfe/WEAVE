const links = [
  { label: "Overview", icon: "grid_view", href: "#overview", active: true },
  { label: "Forecast", icon: "trending_up", href: "#forecast" },
  { label: "Model Weights", icon: "tune", href: "#weights" },
  { label: "Performance", icon: "analytics", href: "#performance" },
  { label: "Extreme Events", icon: "warning", href: "#extreme-events" },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div>
        <a className="brand" href="#overview" aria-label="AWFB dashboard overview">
          <span className="brand__mark">A</span>
          <span className="brand__copy">
            <strong>AWFB</strong>
            <span>Adaptive Weather<br />Forecast Blending</span>
          </span>
        </a>

        <div className="sidebar__label">Workspace</div>
        <nav className="sidebar__nav" aria-label="Main navigation">
          {links.map((link) => (
            <a
              href={link.href}
              className={"sidebar__link" + (link.active ? " is-active" : "")}
              key={link.label}
              aria-current={link.active ? "page" : undefined}
            >
              <span className="material-symbols-outlined" aria-hidden="true">{link.icon}</span>
              <span>{link.label}</span>
            </a>
          ))}
        </nav>
      </div>

      <div className="sidebar__footer">
        <span className="online-dot" />
        <span>System Online</span>
        <span className="sidebar__footer-tag">DEMO</span>
      </div>
    </aside>
  );
}

export default Sidebar;
