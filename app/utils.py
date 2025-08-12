import math

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def busy_bucket(n: int) -> str:
    n = n or 0
    if n >= 7: return "High"
    if n >= 3: return "Moderate"
    return "Low"

def parse_menu_terms(s: str):
    return [t.strip() for t in (s or "").replace("+", ",").split(",") if t.strip()]

def parse_prices(s: str):
    out = []
    for p in (s or "").split(","):
        p = p.strip()
        if not p: continue
        try: out.append(int(p))
        except: pass
    return out

def parse_busy_levels(s: str):
    valid = {"low","moderate","high"}
    return {w.capitalize() for w in (x.strip().lower() for x in (s or "").split(",")) if w in valid}

def truthy(s: str):
    return str(s).lower() in {"1","true","t","yes","y"}