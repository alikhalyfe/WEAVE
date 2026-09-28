"""Cities tracked on the live overview map. Names and states only --
coordinates always come from the Open-Meteo geocoding API, never typed in."""

from src.live import openmeteo

# 24 cities spanning every region. Kept modest because each new place costs
# ~120 Open-Meteo call-units to learn (free tier: 5,000/hour, 10,000/day);
# search still reaches any place in India.
TRACKED_CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Bengaluru", "Karnataka"), ("Hyderabad", "Telangana"),
    ("Chennai", "Tamil Nadu"), ("Kolkata", "West Bengal"), ("Ahmedabad", "Gujarat"), ("Pune", "Maharashtra"),
    ("Jaipur", "Rajasthan"), ("Lucknow", "Uttar Pradesh"), ("Nagpur", "Maharashtra"), ("Bhopal", "Madhya Pradesh"),
    ("Patna", "Bihar"), ("Bhubaneswar", "Odisha"), ("Guwahati", "Assam"), ("Thiruvananthapuram", "Kerala"),
    ("Srinagar", "Jammu and Kashmir"), ("Dehradun", "Uttarakhand"), ("Raipur", "Chhattisgarh"), ("Ranchi", "Jharkhand"),
    ("Chandigarh", "Chandigarh"), ("Panaji", "Goa"), ("Visakhapatnam", "Andhra Pradesh"), ("Leh", "Ladakh"),
]


def resolve(name: str, state: str) -> dict | None:
    """Best geocoding match for name within state (largest population),
    or None if the geocoder doesn't know it."""
    results = openmeteo.search(name, count=10)
    in_state = [r for r in results if r["state"] and state.lower() in r["state"].lower()]
    pool = in_state or results
    if not pool:
        return None
    return max(pool, key=lambda r: r["population"] or 0)
