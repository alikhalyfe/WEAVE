import { useEffect, useState } from "react";

export async function api(path, options) {
  const res = await fetch("/api" + path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ? JSON.stringify(body.detail) : res.statusText);
  return body;
}

export function qs(params) {
  const s = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ).toString();
  return s ? "?" + s : "";
}

/** GET /api{path}; re-fetches when path changes, keeps the last good data while loading. */
export function useApi(path) {
  const [state, setState] = useState({ path: null, data: null, error: null });
  useEffect(() => {
    if (!path) return;
    let live = true;
    api(path)
      .then((data) => live && setState({ path, data, error: null }))
      .catch((error) => live && setState((s) => ({ ...s, path, error })));
    return () => {
      live = false;
    };
  }, [path]);
  return { data: state.data, error: state.error, loading: Boolean(path) && state.path !== path };
}
