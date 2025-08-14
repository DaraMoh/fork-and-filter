from sqlalchemy import func as sa_func
from app import db
from app.models import Restaurant
from app.providers.overpass import search as osm_search
from app.utils.cache import get as cache_get, put as cache_put

def enrich_from_osm(lat, lng, radius_km, terms_csv=None, ttl=3600, limit=60):
    # Cache key per area/terms/limit
    key = f"osm:{round(lat,3)}:{round(lng,3)}:{int(radius_km*1000)}:{(terms_csv or '').lower()}:{int(limit)}"
    data = cache_get(key, ttl_seconds=ttl)
    if data is None:
        cuisines = [t.strip() for t in (terms_csv or "").split(",") if t.strip()]
        data = osm_search(lat, lng, int(radius_km*1000), limit=limit, cuisines=cuisines)
        cache_put(key, data)

    added = updated = 0
    for r in data:
        if (r.get("lat") is None) or (r.get("lng") is None) or not r.get("name"):
            continue
        existing = None
        if hasattr(Restaurant, "external_id") and hasattr(Restaurant, "source") and r.get("external_id"):
            existing = Restaurant.query.filter_by(source=r["source"], external_id=r["external_id"]).first()
        if not existing:
            existing = Restaurant.query.filter(
                sa_func.lower(Restaurant.name) == (r["name"] or "").lower(),
                sa_func.abs(Restaurant.lat - r["lat"]) < 0.0005,
                sa_func.abs(Restaurant.lng - r["lng"]) < 0.0005,
            ).first()

        if existing:
            existing.price_tier = r["price_tier"]
            existing.halal = r["halal"]
            existing.menu = r["menu"]
            existing.neighborhood = r["neighborhood"]
            if hasattr(existing, "external_id"): existing.external_id = r.get("external_id")
            if hasattr(existing, "source"):      existing.source = r.get("source")
            updated += 1
        else:
            obj = Restaurant(
                name=r["name"], lat=r["lat"], lng=r["lng"],
                price_tier=r["price_tier"], halal=r["halal"],
                menu=r["menu"], neighborhood=r["neighborhood"],
            )
            if hasattr(Restaurant, "external_id"): obj.external_id = r.get("external_id")
            if hasattr(Restaurant, "source"):      obj.source = r.get("source")
            db.session.add(obj); added += 1

    db.session.commit()
    return added, updated, len(data)
