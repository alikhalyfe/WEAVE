function ForecastCard({ label, value, unit, icon, accent, detail, active, onClick, alert }) {
  const Tag = onClick ? "button" : "article";
  return (
    <Tag className={"forecast-card" + (active ? " is-active" : "")} onClick={onClick} type={onClick ? "button" : undefined}
      aria-pressed={onClick ? Boolean(active) : undefined}>
      <div className="forecast-card__heading">
        <span className={"forecast-card__icon forecast-card__icon--" + accent}>
          <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
        </span>
        <span>{label}</span>
        {alert && <span className="forecast-card__alert"><span className="material-symbols-outlined" aria-hidden="true">warning</span>{alert}</span>}
      </div>
      <div className="forecast-card__reading">
        <strong>{value}</strong>
        <span>{unit}</span>
      </div>
      <p>{detail}</p>
    </Tag>
  );
}

export default ForecastCard;
