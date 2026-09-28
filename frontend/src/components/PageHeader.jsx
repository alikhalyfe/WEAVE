import SearchBox from "./SearchBox";

/** Top bar for every page: title, a data-provenance badge and place search. */
function PageHeader({ eyebrow, title, badge, children, search = true }) {
  return (
    <header className="topbar">
      <div className="topbar__title">
        <span className="topbar__eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
      </div>
      <div className="topbar__controls">
        {children}
        {search && <SearchBox compact />}
        {badge}
      </div>
    </header>
  );
}

/** Where the numbers on this page come from, stated explicitly. */
export function SourceBadge({ kind, detail }) {
  const live = kind === "live";
  return (
    <span className={"source-badge" + (live ? " is-live" : " is-historical")} title={detail}>
      <i />
      {live ? "Live" : "Historical replay · 2025"}
      {detail && <small>{detail}</small>}
    </span>
  );
}

export default PageHeader;
