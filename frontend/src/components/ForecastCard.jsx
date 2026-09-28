function ForecastCard({ label, value, unit, icon, accent, detail }) {
  return (
    <article className="forecast-card">
      <div className="forecast-card__heading">
        <span className={"forecast-card__icon forecast-card__icon--" + accent}>
          <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
        </span>
        <span>{label}</span>
      </div>
      <div className="forecast-card__reading">
        <strong>{value}</strong>
        <span>{unit}</span>
      </div>
      <p>{detail}</p>
    </article>
  );
}

export default ForecastCard;
