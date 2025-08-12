from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, abort
from sqlalchemy import func
from .models import Restaurant, Checkin
from . import db
from .utils import haversine_km, busy_bucket, parse_menu_terms, parse_busy_levels, parse_prices, truthy

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/search")
def search():
    # --- Parse inputs (defaults: Dallas center) ---
    try:
        lat = float(request.args.get("lat", "32.7767"))
        lng = float(request.args.get("lng", "-96.7970"))
        radius_km = float(request.args.get("radius_km", "5"))
    except ValueError:
        abort(400, "Invalid lat/lng/radius")

    terms = parse_menu_terms(request.args.get("terms", ""))
    prices = parse_prices(request.args.get("prices", ""))
    halal_only = truthy(request.args.get("halal", "false"))
    busy_filter = parse_busy_levels(request.args.get("busy", ""))  # set()

    # --- Base query: apply structured filters first ---
    q = db.session.query(Restaurant)
    if prices:
        q = q.filter(Restaurant.price_tier.in_(prices))
    if halal_only:
        q = q.filter(Restaurant.halal.is_(True))
    if terms:
        for t in terms:
            q = q.filter(Restaurant.menu.ilike(f"%{t}%"))

    restaurants = q.all()

    # --- Recent check-ins (last 60 min) -> counts dict ---
    recent_cutoff = datetime.utcnow() - timedelta(minutes=60)
    counts_rows = (
        db.session.query(Checkin.restaurant_id, func.count(Checkin.id))
        .filter(Checkin.created_at >= recent_cutoff)
        .group_by(Checkin.restaurant_id)
        .all()
    )
    counts = {rid: cnt for (rid, cnt) in counts_rows}

    # --- Distance filter + busyness bucket ---
    items = []
    for r in restaurants:
        dist = haversine_km(lat, lng, r.lat, r.lng)
        if dist > radius_km:
            continue

        busy_count = counts.get(r.id, 0)
        level = busy_bucket(busy_count)
        if busy_filter and level not in busy_filter:
            continue

        items.append({
            "id": r.id,
            "name": r.name,
            "lat": r.lat,
            "lng": r.lng,
            "distance_km": round(dist, 2),
            "price": r.price_tier or 0,
            "halal": bool(r.halal),
            "busy": level,
        })

    # --- Sort by distance asc, then busyness (High > Low) ---
    rank = {"High": 0, "Moderate": 1, "Low": 2}
    items.sort(key=lambda x: (x["distance_km"], rank.get(x["busy"], 3)))
    items = items[:100]

    return render_template("_results.html", results=items, count=len(items))