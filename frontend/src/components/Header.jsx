import { VARIABLES } from "../format";

function Header({ meta, location, variable, lead, time, onChange, status }) {
  const locations = meta?.locations || [];
  const [min, max] = meta ? meta.evaluation_period.map((t) => t.replace(" ", "T").slice(0, 16)) : ["", ""];

  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__eyebrow">RESEARCH / 2025 REPLAY · 5 MAHARASHTRA SITES</span>
        <h1>Historical verification</h1>
      </div>

      <div className="topbar__controls">
        <label className="topbar__select">
          <span>Location</span>
          <select value={location || ""} onChange={(e) => onChange({ location: e.target.value })} aria-label="Location">
            {locations.map((l) => <option key={l.location}>{l.location}</option>)}
          </select>
        </label>
        <label className="topbar__select">
          <span>Variable</span>
          <select value={variable} onChange={(e) => onChange({ variable: e.target.value })} aria-label="Variable">
            {Object.entries(VARIABLES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
        <label className="topbar__select topbar__select--lead">
          <span>Lead time</span>
          <select value={lead} onChange={(e) => onChange({ lead: Number(e.target.value) })} aria-label="Lead time">
            {(meta?.lead_times_hours || [6, 12, 24]).map((h) => <option key={h} value={h}>{h} hours</option>)}
          </select>
        </label>
        <label className="topbar__select topbar__select--time">
          <span>Issued (UTC)</span>
          <input type="datetime-local" step="3600" min={min} max={max} value={time ? time.slice(0, 16) : ""}
            onChange={(e) => e.target.value && onChange({ time: e.target.value.slice(0, 13) + ":00:00" })} aria-label="Issue time" />
        </label>
        <span className={"system-status" + (status === "online" ? "" : " is-" + status)}>
          <i /> {status === "online" ? "API online" : status === "loading" ? "Connecting" : "API offline"}
        </span>
      </div>
    </header>
  );
}

export default Header;
