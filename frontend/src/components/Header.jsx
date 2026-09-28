function Header() {
  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__eyebrow">WEAVE / WEATHER INTELLIGENCE</span>
        <h1>Weather Forecast Intelligence</h1>
      </div>

      <div className="topbar__controls">
        <label className="topbar__select">
          <span>Region</span>
          <select defaultValue="Maharashtra" aria-label="Region">
            <option>Maharashtra</option>
            <option>Gujarat</option>
            <option>Rajasthan</option>
            <option>Karnataka</option>
          </select>
        </label>
        <label className="topbar__select topbar__select--lead">
          <span>Lead time</span>
          <select defaultValue="12 Hours" aria-label="Lead time">
            <option>6 Hours</option>
            <option>12 Hours</option>
            <option>24 Hours</option>
          </select>
        </label>
        <span className="system-status"><i /> System Online</span>
      </div>
    </header>
  );
}

export default Header;
