function DashboardCard({ title, icon, children, className = "", subtitle, action, id }) {
  return (
    <section id={id} className={"dashboard-card " + className}>
      <div className="dashboard-card__header">
        <div className="dashboard-card__heading">
          {icon && <span className="material-symbols-outlined dashboard-card__icon" aria-hidden="true">{icon}</span>}
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export default DashboardCard;
