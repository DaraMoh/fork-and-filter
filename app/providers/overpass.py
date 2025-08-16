import requests

URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "ForkFilter/0.1 (contact: you@example.com)"}

def _synth_desc(tags, halal):
    parts = []
    if tags.get("cuisine"):
        # "mexican;tacos" -> "mexican, tacos"
        parts.append(tags["cuisine"].replace(";", ", "))
    if halal:
        parts.append("Halal-friendly")
    if tags.get("opening_hours"):
        parts.append(f"Hours: {tags['opening_hours']}")
    return " • ".join(parts) or None

def search(lat, lng, radius_m, limit=80, cuisines=None):
    q = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|fast_food|cafe|food_court|ice_cream|bar"](around:{int(radius_m)},{lat},{lng});
      way["amenity"~"restaurant|fast_food|cafe|food_court|ice_cream|bar"](around:{int(radius_m)},{lat},{lng});
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
        cuisine_tag = tags.get("cuisine") or ""
        halal_tag = (tags.get("diet:halal") or tags.get("halal") or "")
        halal = str(halal_tag).lower() in ("yes", "true", "1")

        # coords
        if el.get("type") == "node":
            lat_b, lng_b = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat_b, lng_b = c.get("lat"), c.get("lon")

        # soft cuisine filter if provided
        if terms:
            blob = f"{(name or '')} {cuisine_tag}".lower()
            if not any(t in blob for t in terms):
                continue

        # pull extra details
        website = tags.get("website") or tags.get("contact:website")
        phone = tags.get("contact:phone") or tags.get("phone")
        opening_hours = tags.get("opening_hours")
        desc = tags.get("description") or _synth_desc(tags, halal)

        out.append({
            "source": "osm",
            "external_id": f"osm:{el.get('type')}:{el.get('id')}",
            "name": name or "Unnamed",
            "lat": lat_b,
            "lng": lng_b,
            "price_tier": None,
            "halal": halal,
            "menu": cuisine_tag,
            "neighborhood": "DFW",
            "description": desc,
            "website": website,
            "phone": phone,
            "opening_hours": opening_hours,
            # If present, you can also surface tags.get("wikidata")
            "wikidata": tags.get("wikidata"),
        })
        if len(out) >= int(limit):
            break

    return out