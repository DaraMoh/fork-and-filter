import os
import requests

BASE = "https://places-api.foursquare.com"
API_KEY = (os.getenv("FOURSQUARE_API_KEY") or "").strip()
if not API_KEY:
    raise RuntimeError("Missing FOURSQUARE_API_KEY (.env)")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",     # Bearer + service API key
    "Accept": "application/json",
    "X-Places-Api-Version": "2025-06-17",     # YYYY-MM-DD
}

def _extract_coords(b: dict):
    """
    Try multiple places Foursquare may put coordinates.
    Returns (lat, lng) or (None, None)
    """
    g = (b.get("geocodes") or {})
    for key in ("main", "roof", "drop_off", "front_door", "road"):
        m = g.get(key) or {}
        lat, lng = m.get("latitude"), m.get("longitude")
        if lat is not None and lng is not None:
            return lat, lng

    # Some responses include point under location (rare)
    loc = b.get("location") or {}
    for k in ("lat", "latitude"):
        for kk in ("lng", "longitude"):
            if k in loc and kk in loc:
                return loc[k], loc[kk]

    return None, None

def search(lat, lng, radius_m, query=None, price_csv=None, categories="13065", limit=50):
    """
    Normalize to your Restaurant schema: name, lat, lng, price_tier, halal, menu, neighborhood, source, external_id.
    """
    radius_m = max(1, min(int(radius_m), 50000))   # <= 50km
    limit = max(1, min(int(limit), 50))

    params = {
        "ll": f"{lat},{lng}",
        "radius": radius_m,
        "limit": limit,
        "sort": "RELEVANCE",
        "categories": categories,                  # 13065 = Restaurants
        # Request explicit fields so geocodes are guaranteed in the payload
        "fields": "fsq_id,name,geocodes,categories,price,location",
    }
    if query:
        params["query"] = query
    if price_csv:
        params["price"] = price_csv               # "1,2,3,4"

    resp = requests.get(f"{BASE}/places/search", headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    results = (resp.json() or {}).get("results", [])

    out = []
    for b in results:
        lat_b, lng_b = _extract_coords(b)
        cats = [c.get("name") for c in (b.get("categories") or []) if c.get("name")]
        price = b.get("price")                     # int 1..4 or None
        price_tier = int(price) if isinstance(price, int) else None
        halal = any("halal" in (c or "").lower() for c in cats)
        loc = b.get("location") or {}
        neighborhood = loc.get("locality") or "DFW"

        out.append({
            "source": "foursquare",
            "external_id": b.get("fsq_id"),
            "name": b.get("name"),
            "lat": lat_b,
            "lng": lng_b,
            "price_tier": price_tier,
            "halal": halal,
            "menu": "|".join(cats[:8]) if cats else (query or ""),
            "neighborhood": neighborhood,
        })
    return out
