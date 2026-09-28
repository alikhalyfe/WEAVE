function RegionalMapPlaceholder() {
  return (
    <div className="map-placeholder">
      <div className="map-placeholder__toolbar">
        <span><i /> REGIONAL PRECIPITATION VIEW</span>
        <span className="map-placeholder__chip">DEMO OVERLAY</span>
      </div>
      <div className="map-placeholder__canvas" role="img" aria-label="Illustrative regional weather map placeholder">
        <svg viewBox="0 0 720 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <defs>
            <pattern id="map-lines" width="36" height="36" patternUnits="userSpaceOnUse">
              <path d="M 36 0 L 0 0 0 36" fill="none" stroke="#d9e4e4" strokeWidth="1" />
            </pattern>
            <radialGradient id="rain-area">
              <stop offset="0%" stopColor="#2563eb" stopOpacity=".74" />
              <stop offset="62%" stopColor="#38bdf8" stopOpacity=".45" />
              <stop offset="100%" stopColor="#7dd3fc" stopOpacity=".02" />
            </radialGradient>
          </defs>
          <rect width="720" height="300" fill="#f2f7f5" />
          <rect width="720" height="300" fill="url(#map-lines)" />
          <path d="M473 -20 C422 48 520 89 461 149 C423 189 500 236 449 320" fill="none" stroke="#c2e1e9" strokeWidth="34" opacity=".55" />
          <path d="M473 -20 C422 48 520 89 461 149 C423 189 500 236 449 320" fill="none" stroke="#fff" strokeWidth="2" opacity=".8" />
          <path d="M191 29 L323 48 L355 116 L325 222 L233 263 L164 191 L147 88 Z" fill="#e3ece3" stroke="#758b89" strokeWidth="2" strokeDasharray="6 5" />
          <ellipse cx="256" cy="137" rx="125" ry="90" fill="url(#rain-area)" />
          <ellipse cx="306" cy="184" rx="80" ry="52" fill="url(#rain-area)" opacity=".8" />
          <path d="M159 133 C207 82 282 88 337 127 C368 149 343 181 302 193 C249 211 188 185 159 157" fill="none" stroke="#0284c7" strokeWidth="2" opacity=".5" />
          <path d="M180 136 C221 105 280 106 319 134 C338 147 323 169 290 180 C252 191 206 174 180 153" fill="none" stroke="#0369a1" strokeWidth="1.5" opacity=".58" />
          <g>
            <circle cx="215" cy="131" r="10" fill="#2563eb" opacity=".15" /><circle cx="215" cy="131" r="4" fill="#2563eb" stroke="#fff" strokeWidth="2" />
            <circle cx="271" cy="163" r="13" fill="#2563eb" opacity=".18" /><circle cx="271" cy="163" r="4" fill="#2563eb" stroke="#fff" strokeWidth="2" />
            <circle cx="302" cy="104" r="9" fill="#0d9488" opacity=".15" /><circle cx="302" cy="104" r="4" fill="#0d9488" stroke="#fff" strokeWidth="2" />
          </g>
          <text x="225" y="124" className="map-label">Mumbai</text>
          <text x="281" y="156" className="map-label">Pune</text>
          <text x="312" y="97" className="map-label">Nashik</text>
          <text x="506" y="92" className="map-title">MAHARASHTRA</text>
          <text x="506" y="112" className="map-caption">ILLUSTRATIVE RAINFALL FIELD</text>
          <text x="506" y="245" className="map-caption">75–95 MM EXPECTED</text>
        </svg>
        <div className="map-placeholder__legend">
          <span>Precipitation</span>
          <i className="legend-low" /> Light
          <i className="legend-medium" /> Moderate
          <i className="legend-high" /> Heavy
        </div>
      </div>
    </div>
  );
}

export default RegionalMapPlaceholder;
