import { useEffect, useState } from "react";

// Same-origin in dev (Vite proxy) and when the API serves the build; on
// Vercel, VITE_API_BASE points at the Render service.
const BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

export async function api(path, options) {
  const res = await fetch(BASE + "/api" + path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = body.detail;
    const err = new Error(typeof d === "string" ? d : d?.message || (d ? JSON.stringify(d) : res.statusText));
    err.status = res.status;
    err.relay = d?.relay === true;
    throw err;
  }
  return body;
}

export function qs(params) {
  const s = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();
  return s ? "?" + s : "";
}

/** GET /api{path}; re-fetches when path changes, keeps the last good data while loading.
 * With pollMs, re-fetches on an interval while `poll(data)` returns true. */
export function useApi(path, { pollMs, poll } = {}) {
  const [state, setState] = useState({ path: null, data: null, error: null, tick: 0 });
  useEffect(() => {
    if (!path) return;
    let live = true;
    api(path)
      .then((data) => live && setState((s) => ({ ...s, path, data, error: null })))
      .catch((error) => live && setState((s) => ({ ...s, path, error })));
    return () => {
      live = false;
    };
  }, [path, state.tick]);
  const again = pollMs && state.data && poll?.(state.data);
  useEffect(() => {
    if (!again) return;
    const id = setTimeout(() => setState((s) => ({ ...s, tick: s.tick + 1 })), pollMs);
    return () => clearTimeout(id);
  }, [again, pollMs, state.data]);
  return { data: state.data, error: state.error, loading: Boolean(path) && state.path !== path };
}
