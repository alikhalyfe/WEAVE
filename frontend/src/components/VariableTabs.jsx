import { VARIABLES } from "../format";

function VariableTabs({ value, onChange }) {
  return (
    <div className="segmented" role="tablist" aria-label="Variable">
      {Object.entries(VARIABLES).map(([k, v]) => (
        <button type="button" role="tab" key={k} aria-selected={k === value} className={k === value ? "is-active" : ""} onClick={() => onChange(k)}>
          <span className="material-symbols-outlined" aria-hidden="true">{v.icon}</span>{v.label}
        </button>
      ))}
    </div>
  );
}

export default VariableTabs;
