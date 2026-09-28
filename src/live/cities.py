"""Cities tracked on the live overview map. Names and states only --
coordinates always come from the Open-Meteo geocoding API, never typed in."""

from src.live import openmeteo

TRACKED_CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"), ("Bengaluru", "Karnataka"), ("Hyderabad", "Telangana"),
    ("Ahmedabad", "Gujarat"), ("Chennai", "Tamil Nadu"), ("Kolkata", "West Bengal"), ("Surat", "Gujarat"),
    ("Pune", "Maharashtra"), ("Jaipur", "Rajasthan"), ("Lucknow", "Uttar Pradesh"), ("Kanpur", "Uttar Pradesh"),
    ("Nagpur", "Maharashtra"), ("Indore", "Madhya Pradesh"), ("Bhopal", "Madhya Pradesh"),
    ("Visakhapatnam", "Andhra Pradesh"), ("Patna", "Bihar"), ("Vadodara", "Gujarat"), ("Ludhiana", "Punjab"),
    ("Agra", "Uttar Pradesh"), ("Nashik", "Maharashtra"), ("Varanasi", "Uttar Pradesh"),
    ("Srinagar", "Jammu and Kashmir"), ("Aurangabad", "Maharashtra"), ("Amritsar", "Punjab"),
    ("Ranchi", "Jharkhand"), ("Guwahati", "Assam"), ("Chandigarh", "Chandigarh"),
    ("Thiruvananthapuram", "Kerala"), ("Kochi", "Kerala"), ("Coimbatore", "Tamil Nadu"),
    ("Madurai", "Tamil Nadu"), ("Bhubaneswar", "Odisha"), ("Raipur", "Chhattisgarh"),
    ("Dehradun", "Uttarakhand"), ("Shimla", "Himachal Pradesh"), ("Jodhpur", "Rajasthan"),
    ("Panaji", "Goa"), ("Mangaluru", "Karnataka"), ("Leh", "Ladakh"), ("Port Blair", "Andaman and Nicobar"),
    ("Gangtok", "Sikkim"), ("Shillong", "Meghalaya"), ("Imphal", "Manipur"),
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
