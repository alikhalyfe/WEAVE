"""Plain-language daily outlook and IMD-style hazard labels.

All wording is derived mechanically from numbers WEAVE computed (the
blended forecast, the 51-member ECMWF ensemble, the place's ERA5 normals);
nothing is written by hand per forecast. References:

* IMD rainfall categories (24-h accumulation): very light 0.1-2.4 mm,
  light 2.5-15.5, moderate 15.6-64.4, heavy 64.5-115.5, very heavy
  115.6-204.4, extremely heavy >= 204.5.
* IMD heat wave: plains Tmax >= 40 °C (hills >= 30 °C) and departure from
  normal >= 4.5 °C (severe >= 6.5 °C); or Tmax >= 45 °C (severe >= 47 °C).
  WEAVE's "normal" is the ERA5 mean for the same +-15 days over the last 2
  years (IMD uses 30-year station normals), and "hills" means grid-cell
  elevation >= 1000 m. IMD's coastal-station criterion is not applied.
* Wind wording follows the Beaufort scale (km/h).
"""

from __future__ import annotations

RAIN_CATEGORIES = [  # (lower bound mm/day, IMD category)
    (204.5, "extremely heavy rain"),
    (115.6, "very heavy rain"),
    (64.5, "heavy rain"),
    (15.6, "moderate rain"),
    (2.5, "light rain"),
    (0.1, "very light rain"),
]
BEAUFORT = [  # (lower bound km/h, description)
    (89, "storm-force winds"), (75, "severe gale"), (62, "gale-force winds"), (50, "near-gale winds"),
    (39, "strong winds"), (29, "fresh winds"), (20, "a moderate breeze"), (12, "a gentle breeze"),
    (6, "a light breeze"), (0, "calm air"),
]
HIGH_WIND_KMH = 39  # Beaufort 6 ("strong breeze") and above
HILLS_ELEVATION_M = 1000


def rain_category(mm: float | None) -> str | None:
    if mm is None:
        return None
    return next((name for lo, name in RAIN_CATEGORIES if mm >= lo), None)


def wind_words(kmh: float | None) -> str:
    return next(name for lo, name in BEAUFORT if (kmh or 0) >= lo)


def heat_wave(tmax: float | None, normal: float | None, hills: bool) -> str | None:
    """'severe heat wave' / 'heat wave' / None under IMD-style criteria."""
    if tmax is None:
        return None
    if tmax >= 47:
        return "severe heat wave"
    if tmax >= 45:
        return "heat wave"
    base = 30 if hills else 40
    if normal is None or tmax < base:
        return None
    dep = tmax - normal
    if dep >= 6.5:
        return "severe heat wave"
    if dep >= 4.5:
        return "heat wave"
    return None


def sky_words(cloud: float | None) -> tuple[str, str]:
    """(words, material icon) from mean daytime cloud cover (%)."""
    if cloud is None:
        return "", "partly_cloudy_day"
    if cloud < 20:
        return "Sunny", "sunny"
    if cloud < 50:
        return "Partly cloudy", "partly_cloudy_day"
    if cloud < 80:
        return "Mostly cloudy", "cloud"
    return "Overcast", "cloud"


def temp_words(tmax: float | None) -> str:
    if tmax is None:
        return ""
    for lo, word in [(40, "very hot"), (35, "hot"), (30, "warm"), (22, "pleasant"), (15, "cool"), (-99, "cold")]:
        if tmax >= lo:
            return word
    return ""


def describe_day(day: dict) -> dict:
    """day: high, low, normal_high, rain_mm, rain_chance (0-1 or None),
    wind_kmh, cloud, hazards. Returns headline, sentence and icon."""
    sky, icon = sky_words(day.get("cloud"))
    rain = rain_category(day.get("rain_mm"))
    chance = day.get("rain_chance")
    showers_possible = not rain and chance is not None and chance >= 0.3

    if rain in {"heavy rain", "very heavy rain", "extremely heavy rain"}:
        icon, headline = "thunderstorm", rain.capitalize()
    elif rain in {"moderate rain", "light rain"}:
        icon, headline = "rainy", rain.capitalize()
    elif rain == "very light rain" and chance is not None and chance >= 0.5:
        icon, headline = "rainy_light", f"{sky + ', ' if sky else ''}light showers".capitalize()
    elif (rain == "very light rain" and (chance is None or chance >= 0.3)) or showers_possible:
        icon, headline = "rainy_light", f"{sky + ', ' if sky else ''}chance of a shower".capitalize()
    else:
        headline = ", ".join(x for x in (sky or "Dry", temp_words(day.get("high"))) if x).capitalize()

    parts = []
    if day.get("high") is not None:
        hl = f"High {day['high']:.0f}°C"
        if day.get("low") is not None:
            hl += f", low {day['low']:.0f}°C"
        dep = day["high"] - day["normal_high"] if day.get("normal_high") is not None else 0
        if abs(dep) >= 1.5:
            hl += f", {abs(dep):.0f}°C {'above' if dep > 0 else 'below'} normal"
        parts.append(hl + ".")
    if rain and day["rain_mm"] >= 1:
        parts.append(f"{rain.capitalize()}, around {day['rain_mm']:.0f} mm.")
    elif rain:
        parts.append("A little drizzle at most.")
    elif showers_possible:
        parts.append("Mostly dry, but a shower is possible.")
    else:
        parts.append("Staying dry.")
    if chance is not None:
        parts.append(f"Chance of rain {round(chance * 100)}%.")
    if day.get("wind_kmh") is not None:
        parts.append(f"{wind_words(day['wind_kmh']).capitalize()}, up to {day['wind_kmh']:.0f} km/h.")
    for h in day.get("hazards", []):
        if h["level"] in ("warning", "watch"):
            parts.append(h["sentence"])
    if any(h["level"] == "warning" for h in day.get("hazards", [])):
        icon = "warning"
    return {"headline": headline, "text": " ".join(parts), "icon": icon}
