// Recently viewed places (per browser convenience only; never shown as data).
const KEY = "weave.recentPlaces";

export function readRecent() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}

export function rememberPlace(place) {
  try {
    const rest = readRecent().filter((p) => !(p.name === place.name && p.state === place.state));
    localStorage.setItem(KEY, JSON.stringify([place, ...rest].slice(0, 6)));
  } catch {
    /* storage unavailable */
  }
}
