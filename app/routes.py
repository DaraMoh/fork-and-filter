# app/routes.py
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, abort, current_app
from sqlalchemy import func
from .models import Restaurant, Checkin
from . import db
from .utils import (
    haversine_km,
    busy_bucket,
    parse_menu_terms,
    parse_busy_levels,
    parse_prices,
    truthy,
)
from .services.osm_enrich import enrich_from_osm

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/search")
def search():
    # ---- Parse inputs (defaults: Dallas) ----
    try:
        lat = float(request.args.get("lat", "32.7767"))
        lng = float(request.args.get("lng", "-96.7970"))
        radius_km = float(request.args.get("radius_km", "5"))
    except ValueError:
        abort(400, "Invalid lat/lng/radius")

    terms_str = request.args.get("terms", "")
    terms = parse_menu_terms(terms_str)
    prices = parse_prices(request.args.get("prices", ""))
    halal_only = truthy(request.args.get("halal", "false"))
    busy_filter = parse_busy_levels(request.args.get("busy", ""))  # {"Low","Moderate","High"}

    # ---- Optional: pull fresh OSM data BEFORE querying DB ----
    # Triggered when the UI passes ?enrich=1 (e.g., your "Load more nearby" button)
    if request.args.get("enrich") == "1":
        try:
            enrich_limit = int(request.args.get("enrich_limit", "120"))
        except ValueError:
            enrich_limit = 120
        try:
            added, updated, total = enrich_from_osm(
                lat=lat,
                lng=lng,
                radius_km=radius_km,
                terms_csv=terms_str,
                ttl=3600,            # 1h cache
                limit=enrich_limit,  # allow larger pulls
            )
            current_app.logger.info(f"OSM enrich: +{added} new, {updated} updated (from {total})")
        except Exception as e:
            current_app.logger.warning(f"OSM enrich failed: {e}")

    # ---- Build results (helper closes over inputs above) ----
    def build_results():
        # Base DB filters
        q = db.session.query(Restaurant)
        if prices:
            q = q.filter(Restaurant.price_tier.in_(prices))
        if halal_only:
            q = q.filter(Restaurant.halal.is_(True))
        if terms:
            for t in terms:
                q = q.filter(Restaurant.menu.ilike(f"%{t}%"))

        restaurants = q.all()

        # Recent check-ins (last 60 min) -> counts dict
        recent_cutoff = datetime.utcnow() - timedelta(minutes=60)
        counts_rows = (
            db.session.query(Checkin.restaurant_id, func.count(Checkin.id))
            .filter(Checkin.created_at >= recent_cutoff)
            .group_by(Checkin.restaurant_id)
            .all()
        )
        counts = {rid: cnt for (rid, cnt) in counts_rows}

        # Distance + busy bucket + optional busy filter
        items_full = []
        for r in restaurants:
            try:
                dist = haversine_km(lat, lng, r.lat, r.lng)
            except Exception:
                continue
            if dist > radius_km:
                continue

            busy_count = counts.get(r.id, 0)
            level = busy_bucket(busy_count)
            if busy_filter and level not in busy_filter:
                continue

            items_full.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "lat": r.lat,
                    "lng": r.lng,
                    "distance_km": round(dist, 2),
                    "price": r.price_tier or 0,
                    "halal": bool(r.halal),
                    "busy": level,
                    # optional richer fields if present
                    "description": getattr(r, "description", None),
                    "website": getattr(r, "website", None),
                }
            )

        # Sort by (distance asc, then busy desc High>Low)
        rank = {"High": 0, "Moderate": 1, "Low": 2}
        items_full.sort(key=lambda x: (x["distance_km"], rank.get(x["busy"], 3)))
        return items_full

    items_full = build_results()

    # ---- Paging ----
    try:
        page = max(int(request.args.get("page", "1")), 1)
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", "50"))
    except ValueError:
        per_page = 50
    # clamp per_page to a sane range
    per_page = min(max(per_page, 1), 200)

    start = (page - 1) * per_page
    end = start + per_page
    items = items_full[start:end]
    has_more = end < len(items_full)

    return render_template(
        "_results.html",
        results=items,
        count=len(items),
        page=page,
        per_page=per_page,
        has_more=has_more,
        total=len(items_full),
    )


# ---- Minimal check-in endpoint (debounced on the client) ----
@bp.post("/checkin")
def checkin():
    rid = request.form.get("restaurant_id") or request.json.get("restaurant_id")
    if not rid:
        abort(400, "restaurant_id required")
    # Optional: clamp spam in server-side by ignoring duplicates within N seconds per IP+rid
    db.session.add(Checkin(restaurant_id=int(rid), created_at=datetime.utcnow()))
    db.session.commit()
    return ("", 204)
