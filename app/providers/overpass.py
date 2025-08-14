import requests

URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "ForkFilter/0.1 (contact: you@example.com)"}  # be polite

def search(lat, lng, radius_m, limit=80, cuisines=None):
    """
    Fetch restaurants/fast_food from OSM via Overpass.
    cuisines: list[str] like ['tacos','pizza'] used as a soft filter (name/cuisine tags).
    Returns list[dict] normalized to your Restaurant schema.
    """
    q = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|fast_food"](around:{int(radius_m)},{lat},{lng});
      way["amenity"~"restaurant|fast_food"](around:{int(radius_m)},{lat},{lng});
    );
    out center;
    """
    r = requests.post(URL, data={"data": q}, headers=HEADERS, timeout=40)
    r.raise_for_status()
    data = r.json()
    out, terms = [], [t.lower() for t in (cuisines or []) if t]

    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name")
        cuisine = tags.get("cuisine")  # may be "mexican;tacos"
        halal_tag = (tags.get("diet:halal") or tags.get("halal") or "")
        halal = str(halal_tag).lower() in ("yes", "true", "1")

        if el.get("type") == "node":
            lat_b, lng_b = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat_b, lng_b = c.get("lat"), c.get("lon")

        if terms:
            blob = f"{name or ''} {cuisine or ''}".lower()
            if not any(t in blob for t in terms):
                continue

        out.append({
            "source": "osm",
            "external_id": f"osm:{el.get('type')}:{el.get('id')}",
            "name": name or "Unnamed",
            "lat": lat_b,
            "lng": lng_b,
            "price_tier": None,
            "halal": halal,
            "menu": (cuisine or ""),
            "neighborhood": "DFW",
        })
        if len(out) >= int(limit):
            break

    return out
