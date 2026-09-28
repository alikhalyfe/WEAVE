import DashboardCard from "./DashboardCard";

function ModelWeights({ weights }) {
  return (
    <DashboardCard
      id="weights"
      title="Adaptive Model Blending"
      icon="tune"
      subtitle="Dynamic contribution by model"
      className="weights-card"
      action={<span className="card-tag">ACTIVE BLEND</span>}
    >
      <div className="weight-list">
        {weights.map((model) => (
          <div className="weight-row" key={model.name}>
            <div className="weight-row__top">
              <span className="weight-row__name"><i style={{ background: model.color }} />{model.name}</span>
              <strong>{model.value}%</strong>
            </div>
            <div className="weight-track" role="img" aria-label={model.name + " weight " + model.value + " percent"}>
              <span style={{ width: model.value + "%", background: model.color }} />
            </div>
          </div>
        ))}
      </div>
      <div className="weight-total"><span>Combined model weight</span><strong>100%</strong></div>
    </DashboardCard>
  );
}

export default ModelWeights;
