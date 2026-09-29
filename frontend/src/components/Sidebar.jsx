import { motion } from "motion/react";
import { NavLink } from "react-router-dom";

const GROUPS = [
  {
    label: "Live · India",
    links: [
      { to: "/", label: "Overview", icon: "public", end: true },
      { to: "/forecast", label: "Forecast", icon: "trending_up" },
      { to: "/weights", label: "Model Weights", icon: "tune" },
      { to: "/performance", label: "Performance", icon: "analytics" },
      { to: "/extremes", label: "Warnings", icon: "warning" },
      { to: "/operations", label: "Operations", icon: "autorenew" },
    ],
  },
  {
    label: "Research",
    links: [
      { to: "/historical", label: "2025 Replay", icon: "history" },
      { to: "/blend", label: "Blend Tool", icon: "bolt" },
      { to: "/about", label: "Method & Data", icon: "info" },
    ],
  },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div>
        <NavLink className="brand" to="/" aria-label="WEAVE overview">
          <img className="brand__logo" src="/logo-64.png" alt="" width="36" height="36" />
          <span className="brand__copy">
            <strong>WEAVE</strong>
            <span>Adaptive Weather<br />Forecast Blending</span>
          </span>
        </NavLink>

        {GROUPS.map((g) => (
          <div key={g.label}>
            <div className="sidebar__label">{g.label}</div>
            <nav className="sidebar__nav" aria-label={g.label}>
              {g.links.map((link) => (
                <NavLink key={link.to} to={link.to} end={link.end}
                  className={({ isActive }) => "sidebar__link" + (isActive ? " is-active" : "")}>
                  {({ isActive }) => (
                    <>
                      {isActive && <motion.span layoutId="nav-active" className="sidebar__pill" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
                      <span className="material-symbols-outlined" aria-hidden="true">{link.icon}</span>
                      <span>{link.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </nav>
          </div>
        ))}
      </div>

      <div className="sidebar__footer">
        <span className="online-dot" />
        <span>Open-Meteo · ERA5 · SACHET</span>
      </div>
    </aside>
  );
}

export default Sidebar;
