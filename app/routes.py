import os, json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, abort, make_response
from sqlalchemy import func
from .models import Restaurant, Checkin
from . import db
from .utils import haversine_km, busy_bucket, parse_menu_terms, parse_busy_levels, parse_prices, truthy

bp = Blueprint("main", __name__)

# in-memory throttle, might need to change to redis/DB for further prod
_CHECKIN_THROTTLE = {}
_COOLDOWN_MIN = int(os.getenv("CHECKIN_COOLDOWN_MINUTES", "10"))

def _client_ip():
    xf = request.headers.get("X-Forwarded-For")
    if xf:
        return xf.split(",")[0].strip()
    return request.remote_addr or "unknown"

@bp.route("/")
def index():
    return render_template("index.html")

def _get(name, default=None):
    """Read a single value from either query string or form (HTMX uses POST)."""
    return request.values.get(name, default)

def _getlist(name):
    """Read a list (works for ?a=1&a=2 or multi-select POST)."""
    return request.values.getlist(name)

def build_results():
    # --- Parse inputs (defaults: Dallas center) ---
    try:
        lat = float(_get("lat", "32.7767"))
        lng = float(_get("lng", "-96.7970"))
        radius_km = float(_get("radius_km", "5"))
    except ValueError:
        abort(400, "Invalid lat/lng/radius")

    terms = parse_menu_terms(_get("terms", ""))

    # prices may come as multiple values or CSV; handle both
    prices_vals = _getlist("prices")
    if prices_vals:
        prices = [int(p) for p in prices_vals if str(p).isdigit()]
    else:
        prices = parse_prices(_get("prices", ""))

    halal_only = truthy(_get("halal", "false"))
    busy_filter = parse_busy_levels(_get("busy", ""))  # set() of {"Low","Moderate","High"}

    # --- Base query ---
    q = db.session.query(Restaurant)
    if prices:
        q = q.filter(Restaurant.price_tier.in_(prices))
    if halal_only:
        q = q.filter(Restaurant.halal.is_(True))
    if terms:
        for t in terms:
            q = q.filter(Restaurant.menu.ilike(f"%{t}%"))

    restaurants = q.all()

    # --- Recent check-ins (last 60 min) ---
    recent_cutoff = datetime.utcnow() - timedelta(minutes=60)
    counts_rows = (
        db.session.query(Checkin.restaurant_id, func.count(Checkin.id))
        .filter(Checkin.created_at >= recent_cutoff)
        .group_by(Checkin.restaurant_id)
        .all()
    )
    counts = {rid: cnt for (rid, cnt) in counts_rows}

    # --- Distance + busyness ---
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

    # sort: nearest first, then High > Moderate > Low
    rank = {"High": 0, "Moderate": 1, "Low": 2}
    items.sort(key=lambda x: (x["distance_km"], rank.get(x["busy"], 3)))
    return items, len(items)

@bp.route("/search", methods=["GET"])
def search():
    items, count = build_results()
    return render_template("_results.html", results=items, count=count)

@bp.route("/checkin/<int:restaurant_id>", methods=["POST"])
def checkin(restaurant_id):
    # debounce by IP and rest
    ip = _client_ip()
    now = datetime.utcnow()
    key = (ip, restaurant_id)
    last = _CHECKIN_THROTTLE.get(key)
    cooldown = timedelta(minutes=_COOLDOWN_MIN)

    if last and (now - last) < cooldown:
        items, count = build_results(request)
        resp = make_response(render_template("_results.html", results=items, count=count))
        mins_left = max(1,int((cooldown - (now-last)).total_seconds() // 60))
        resp.headers["HX-Trigger"] = json.dumps({"toast": f"Already checked in. Try again in ~{mins_left} minutes."})
        return resp, 200
    
    # record the check-in
    r = Restaurant.query.get_or_404(restaurant_id)
    db.session.add(Checkin(restaurant_id=r.id, created_at=datetime.utcnow()))
    db.session.commit()
    _CHECKIN_THROTTLE[key] = now

    # re-render with the same filters (HTMX includes the form)
    items, count = build_results()
    resp = make_response(render_template("_results.html", results=items, count=count))
    resp.headers["HX-Trigger"] = json.dumps({"toast": "Checked in! Thanks!!!"})
    return resp, 200