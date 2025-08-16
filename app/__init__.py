import os
import click
import time
from pathlib import Path
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func as sa_func
from dotenv import load_dotenv

# Global DB handle
db = SQLAlchemy()


def create_app():
    load_dotenv()

    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        template_folder="templates",
    )

    # Ensure instance dir exists
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Basic config
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=(
            os.getenv("DATABASE_URL")
            or f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    # Init DB + blueprints
    db.init_app(app)
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    # ---------- PWA assets ----------
    @app.route("/manifest.json")
    def manifest():
        pwa_dir = os.path.join(app.root_path, "pwa")
        return send_from_directory(pwa_dir, "manifest.json", mimetype="application/json")

    @app.route("/service-worker.js")
    def service_worker():
        # Served from /static/sw.js
        return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")

    @app.route("/icons/<path:filename>")
    def pwa_icons(filename):
        icons_dir = os.path.join(app.root_path, "pwa", "icons")
        return send_from_directory(icons_dir, filename)

    @app.route("/static/offline.html")
    def offline():
        return app.send_static_file("offline.html")

    # ---------- CLI: init DB ----------
    @app.cli.command("init-db")
    def init_db_command():
        """Create all database tables."""
        with app.app_context():
            db.create_all()
        click.echo("Database initialized")

    # ---------- CLI: quick sanity count ----------
    @app.cli.command("count-restaurants")
    def count_restaurants():
        from .models import Restaurant
        click.echo(f"Restaurants in DB: {Restaurant.query.count()}")

    # ---------- CLI: ingest from Foursquare Places (smart 429 handling + probe logs) ----------
    @app.cli.command("ingest-fsq")
    @click.option("--lat", type=float, required=True)
    @click.option("--lng", type=float, required=True)
    @click.option("--radius-km", type=float, default=8.0, show_default=True)
    @click.option("--terms", type=str, default="", help='Comma list: "tacos,pizza,shawarma"')
    @click.option("--prices", type=str, default="", help='Foursquare price levels "1,2,3,4"')
    @click.option("--categories", type=str, default="13065", show_default=True, help="FSQ categories, e.g. 13065=Restaurants")
    @click.option("--limit", type=int, default=30, show_default=True, help="Max results per request (<=50)")
    @click.option("--delay", type=float, default=1.2, show_default=True, help="Seconds to sleep between term requests")
    @click.option("--max-retries", type=int, default=3, show_default=True, help="Retries per term when 429")
    def ingest_fsq(lat, lng, radius_km, terms, prices, categories, limit, delay, max_retries):
        """Seed restaurants from Foursquare Places into the local DB."""
        import requests
        import random
        from datetime import datetime, timezone
        from email.utils import parsedate_to_datetime
        from requests import Request
        from .models import Restaurant

        click.echo(
            f"Starting ingest-fsq lat={lat} lng={lng} radius_km={radius_km} "
            f"terms={terms!r} prices={prices!r} categories={categories!r} "
            f"limit={limit} delay={delay}s max_retries={max_retries}"
        )

        # Prepare shared params (for debug preview URL)
        probe_params = dict(
            ll=f"{lat},{lng}",
            radius=int(radius_km * 1000),
            limit=int(limit),
            sort="RELEVANCE",
            categories=(categories or None),
        )
        if prices:
            probe_params["price"] = prices

        # Provider header sanity (mask the key)
        try:
            from .providers import foursquare as fsqmod
            h = getattr(fsqmod, "HEADERS", {})
            auth_val = (h.get("Authorization") or "")
            click.echo(f"   (debug) provider headers: Bearer={auth_val.startswith('Bearer ')}, ver={h.get('X-Places-Api-Version')}")
        except Exception:
            pass

        terms_list = [t.strip() for t in (terms or "").split(",") if t.strip()] or [None]

        def _parse_retry_after(hdr: str | None) -> float | None:
            if not hdr:
                return None
            # seconds?
            try:
                return float(hdr)
            except ValueError:
                pass
            # HTTP-date?
            try:
                dt = parsedate_to_datetime(hdr)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return max(0.0, (dt - datetime.now(timezone.utc)).total_seconds())
            except Exception:
                return None

        def fetch_with_backoff(term):
            """Call provider search with retries on 429 honoring Retry-After and reset headers."""
            attempt = 0
            while attempt <= max_retries:
                try:
                    return fsqmod.search(
                        lat=lat, lng=lng, radius_m=int(radius_km * 1000),
                        query=term, price_csv=(prices or None),
                        categories=(categories or None), limit=limit
                    )
                except requests.HTTPError as e:
                    resp = getattr(e, "response", None)
                    code = getattr(resp, "status_code", None)
                    if code != 429:
                        click.echo(f"\n  !! Request failed (HTTP {code}): {e}")
                        return None

                    # Log rate-limit headers
                    rh = resp.headers if resp is not None else {}
                    ra_raw = rh.get("Retry-After")
                    rem = rh.get("RateLimit-Remaining") or rh.get("X-RateLimit-Remaining")
                    reset_raw = rh.get("RateLimit-Reset") or rh.get("X-RateLimit-Reset")
                    click.echo("\n   (rate limited)")
                    click.echo(f"     Retry-After: {ra_raw}")
                    click.echo(f"     Remaining:   {rem}")
                    click.echo(f"     Reset:       {reset_raw}")

                    # Decide wait
                    wait = _parse_retry_after(ra_raw)

                    # If reset epoch is provided, prefer that when no Retry-After
                    if wait is None and reset_raw:
                        try:
                            reset_epoch = float(reset_raw)
                            reset_dt = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
                            wait = max(0.0, (reset_dt - datetime.now(timezone.utc)).total_seconds())
                        except Exception:
                            wait = None

                    # Fallback: if bucket empty, be extra patient; else normal backoff + jitter
                    if wait is None:
                        base = 10.0 if (rem == "0") else 3.0
                        wait = base * (attempt + 1) + random.uniform(0, 0.75)

                    click.echo(f"     → waiting {wait:.1f}s before retry {attempt+1}/{max_retries}")
                    time.sleep(wait)
                    attempt += 1
                    continue
                except Exception as e:
                    click.echo(f"\n  !! Request failed: {e}")
                    return None

            click.echo("  !! Gave up after retries")
            return None

        def upsert_rows(rows):
            added = updated = 0
            for r in rows:
                # require coords and name; treat 0.0 as valid
                if (r.get("lat") is None) or (r.get("lng") is None) or (not r.get("name")):
                    continue

                existing = None
                # Prefer stable external_id/source if model has them
                if hasattr(Restaurant, "external_id") and hasattr(Restaurant, "source") and r.get("external_id"):
                    existing = Restaurant.query.filter_by(
                        source=r.get("source"), external_id=r.get("external_id")
                    ).first()

                if not existing:
                    # Fallback: name + ~50m proximity
                    existing = Restaurant.query.filter(
                        sa_func.lower(Restaurant.name) == (r["name"] or "").lower(),
                        sa_func.abs(Restaurant.lat - r["lat"]) < 0.0005,  # ~55m lat
                        sa_func.abs(Restaurant.lng - r["lng"]) < 0.0005,  # ~45m lng in DFW
                    ).first()

                if existing:
                    existing.price_tier = r["price_tier"]
                    existing.halal = r["halal"]
                    existing.menu = r["menu"]
                    existing.neighborhood = r["neighborhood"]
                    if hasattr(existing, "external_id"):
                        existing.external_id = r.get("external_id")
                    if hasattr(existing, "source"):
                        existing.source = r.get("source")
                    updated += 1
                else:
                    obj = Restaurant(
                        name=r["name"], lat=r["lat"], lng=r["lng"],
                        price_tier=r["price_tier"], halal=r["halal"],
                        menu=r["menu"], neighborhood=r["neighborhood"],
                    )
                    if hasattr(Restaurant, "external_id"):
                        obj.external_id = r.get("external_id")
                    if hasattr(Restaurant, "source"):
                        obj.source = r.get("source")
                    db.session.add(obj)
                    added += 1

            db.session.commit()
            return added, updated

        total_added = total_updated = 0
        for term in terms_list:
            click.echo(f"→ Querying FSQ for term={term!r} …", nl=False)

            # Probe: show the exact URL we’ll hit (no secrets)
            pp = probe_params.copy()
            if term:
                pp["query"] = term
            preview_url = Request(
                "GET",
                "https://places-api.foursquare.com/places/search",
                params=pp
            ).prepare().url
            click.echo(f"\n   (debug) GET {preview_url}")

            rows = fetch_with_backoff(term)
            if rows is None:
                click.echo("")  # newline after nl=False
                continue

            click.echo(f" got {len(rows)} rows")

            missing = sum(
                1 for r in rows
                if (r.get("lat") is None) or (r.get("lng") is None) or (not r.get("name"))
            )
            if missing:
                click.echo(f"   (debug) skipping {missing} rows missing coords or name")

            if rows:
                sample = {k: rows[0].get(k) for k in ("name", "lat", "lng", "price_tier", "halal", "neighborhood")}
                click.echo(f"   (debug) sample: {sample}")

            added, updated = upsert_rows(rows)
            total_added += added
            total_updated += updated
            click.echo(f"   ✓ Upserted: +{added} new, {updated} updated")

            # Small politeness delay between terms
            time.sleep(max(0.0, delay))

        click.echo(f"Done. Total +{total_added} new, {total_updated} updated.")
    

    @app.cli.command("ingest-osm")
    @click.option("--lat", type=float, required=True)
    @click.option("--lng", type=float, required=True)
    @click.option("--radius-km", type=float, default=2.0, show_default=True)
    @click.option("--terms", type=str, default="", help='Comma list to filter by (optional): "tacos,pizza"')
    @click.option("--limit", type=int, default=80, show_default=True)
    def ingest_osm(lat, lng, radius_km, terms, limit):
        """Seed restaurants from OpenStreetMap (Overpass) into the local DB."""
        from .models import Restaurant
        from .providers.overpass import search as osm_search

        click.echo(f"Starting ingest-osm lat={lat} lng={lng} radius_km={radius_km} terms={terms!r} limit={limit}")
        cuisines = [t.strip() for t in terms.split(",") if t.strip()]
        rows = osm_search(lat=lat, lng=lng, radius_m=int(radius_km * 1000), limit=limit, cuisines=cuisines)
        click.echo(f" got {len(rows)} rows")

        added = updated = 0
        for r in rows:
            if (r.get("lat") is None) or (r.get("lng") is None) or (not r.get("name")):
                continue
            existing = None
            if hasattr(Restaurant, "external_id") and hasattr(Restaurant, "source") and r.get("external_id"):
                existing = Restaurant.query.filter_by(source=r.get("source"), external_id=r.get("external_id")).first()
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
        click.echo(f"✓ Upserted: +{added} new, {updated} updated")


    return app
