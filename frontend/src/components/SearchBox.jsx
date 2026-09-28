import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, qs } from "../api";
import { placeUrl } from "../format";
import { readRecent, rememberPlace } from "../recent";

/** Place search limited to India (Open-Meteo geocoding via the API). */
function SearchBox({ autoFocus = false, compact = false }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState("idle");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const listId = useId();
  const box = useRef(null);
  const recent = readRecent();
  const q = query.trim();
  const items = q.length >= 2 ? results : recent;

  useEffect(() => {
    if (q.length < 2) return;
    let live = true;
    const id = setTimeout(() => {
      setStatus("loading");
      api("/live/search" + qs({ q }))
        .then((r) => live && (setResults(r.results), setStatus("done"), setActive(0)))
        .catch(() => live && (setResults([]), setStatus("error")));
    }, 250);
    return () => {
      live = false;
      clearTimeout(id);
    };
  }, [q]);

  useEffect(() => {
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  const choose = (place) => {
    rememberPlace(place);
    setOpen(false);
    setQuery("");
    navigate(placeUrl(place));
  };

  const onKey = (e) => {
    if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, items.length - 1));
    else if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
    else if (e.key === "Enter" && items[active]) choose(items[active]);
    else if (e.key === "Escape") setOpen(false);
    else return;
    e.preventDefault();
  };

  return (
    <div className={"search" + (compact ? " search--compact" : "")} ref={box}>
      <span className="material-symbols-outlined search__icon" aria-hidden="true">search</span>
      <input type="search" role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
        aria-activedescendant={open && items[active] ? `${listId}-${active}` : undefined}
        placeholder="Search any city or town in India" value={query} autoFocus={autoFocus}
        onChange={(e) => (setQuery(e.target.value), setOpen(true))} onFocus={() => setOpen(true)} onKeyDown={onKey} />
      <AnimatePresence>
        {open && (items.length > 0 || q.length >= 2) && (
          <motion.ul id={listId} role="listbox" className="search__list" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.15 }}>
            {q.length < 2 && <li className="search__hint">Recent</li>}
            {q.length >= 2 && status === "loading" && <li className="search__hint">Searching…</li>}
            {q.length >= 2 && status === "error" && <li className="search__hint">Search is unavailable right now.</li>}
            {q.length >= 2 && status === "done" && !results.length && <li className="search__hint">No places in India match “{q}”.</li>}
            {items.map((p, i) => (
              <li key={`${p.name}-${p.latitude}-${p.longitude}`} id={`${listId}-${i}`} role="option" aria-selected={i === active}
                className={i === active ? "is-active" : ""} onPointerEnter={() => setActive(i)} onPointerDown={(e) => (e.preventDefault(), choose(p))}>
                <span className="material-symbols-outlined" aria-hidden="true">location_on</span>
                <span className="search__name">{p.name}</span>
                <span className="search__meta">{[p.district !== p.name ? p.district : null, p.state].filter(Boolean).join(", ")}</span>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

export default SearchBox;
