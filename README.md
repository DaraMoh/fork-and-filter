# Fork & Filter
A fast, map-first restaurant finder for the Dallas–Fort Worth area.
Backend in Flask + SQLAlchemy, frontend in HTMX + Tailwind + Leaflet, packaged as a PWA you can install to your phone/desktop.

## Features
🔎 Filters: menu terms (e.g., shawarma,tacos), price tier ($/$$/$$$), halal-only, radius.
🗺️ Map UI: Leaflet map with Voyager tiles; click any result to zoom + open its popup.
📍 Geolocation: “Use my location” sets center and radius ring; persists to localStorage.
📥 Data sources: OpenStreetMap / Overpass enrichment (triggered via “Load more nearby”) with de-dupe + upsert.
📦 PWA: installable, offline fallback page, service worker caching.
⚡ Snappy UX: HTMX partials, paging (page, per_page), and right-hand drawer with a vertical tab.

## Tech Stack
Backend: Python, Flask, Flask-SQLAlchemy, Click, requests, python-dotenv
DB: SQLite (local) via SQLAlchemy (works with Postgres via DATABASE_URL)
Frontend: HTMX, Tailwind (CDN), Leaflet
PWA: manifest.json, service worker (static/sw.js)

## Getting Started
### 1) Create and activate venv
Windows (PowerShell):
```
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Environment
Create a .env in the project root:
```
# required
SECRET_KEY=dev
# optional (SQLite used if omitted)
DATABASE_URL=sqlite:///instance/app.db

# optional: Foursquare Service API Key for CLI seeding
FOURSQUARE_API_KEY=fsq_...
```

### 3) Initialize the database
Windows:
```
py -m flask --app run.py init-db
```
macOS/Linux:
```
flask --app run.py init-db
```
### 4) Run the app
Windows:
```
py -m flask --app run.py run
```
macOS/Linux:
```
flask --app run.py run
```
Open http://localhost:5000 and allow location!

## Roadmap
- “Open now” via opening_hours parsing.
- Marker clustering for large result sets.
- BestTime API integration (real-time busyness).
- Shareable URLs (persist filters in query string).
- Full integration of Foursquare API

## Acknowledgements
Map data © OpenStreetMap contributors
Tiles © CARTO (Voyager)
Thanks to the Foursquare and Overpass communities for their APIs
