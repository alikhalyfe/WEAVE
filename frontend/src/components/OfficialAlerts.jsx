import { Rise, Stagger } from "./Motion";
import { officialColor } from "../format";

const LANGUAGES = { hi: "Hindi", te: "Telugu", ta: "Tamil", kn: "Kannada", ml: "Malayalam", mr: "Marathi", bn: "Bengali", gu: "Gujarati", or: "Odia", pa: "Punjabi", as: "Assamese", ur: "Urdu" };

function when(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Official warnings from NDMA SACHET, relayed verbatim. */
function OfficialAlerts({ alerts, empty = "No active official warnings.", limit = 8, showDistance = false }) {
  if (!alerts?.length) {
    return <div className="alert-empty"><span className="material-symbols-outlined" aria-hidden="true">verified</span>{empty}</div>;
  }
  return (
    <Stagger as="ul" className="official-list">
      {alerts.slice(0, limit).map((a) => (
        <Rise as="li" key={a.id} className="official-item" style={{ "--sev": officialColor(a) }}>
          <div className="official-item__head">
            <span className="official-item__sev">{a.severity}</span>
            <strong>{a.type}</strong>
            <span className="muted">{a.source}</span>
            {a.language && a.language !== "en" && <span className="official-item__lang" title="Relayed verbatim in the issuing authority's language">{LANGUAGES[a.language] || a.language}</span>}
          </div>
          <p className="official-item__area">{a.area}{showDistance && a.distance_km != null && ` · ${a.distance_km} km away`}</p>
          <p className="official-item__msg">{a.message}</p>
          <span className="official-item__time">{when(a.starts)} – {when(a.ends)} IST</span>
        </Rise>
      ))}
      {alerts.length > limit && <li className="muted">+{alerts.length - limit} more on sachet.ndma.gov.in</li>}
    </Stagger>
  );
}

export default OfficialAlerts;
