import math

# --- geo ---
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0  # km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

# --- parsing helpers ---
def parse_menu_terms(s: str) -> list[str]:
    return [t.strip().lower() for t in (s or "").split(",") if t.strip()]

def parse_prices(s: str) -> list[int]:
    out = []
    for tok in (s or "").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.append(int(tok))
    return out

def parse_busy_levels(s: str) -> set[str]:
    allow = {"low", "moderate", "high"}
    vals = {t.strip().lower() for t in (s or "").split(",") if t.strip()}
    return {v.capitalize() for v in vals if v in allow}

def truthy(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "on"}

# --- busyness bucketing (based on recent check-ins) ---
def busy_bucket(count: int) -> str:
    # tweak thresholds as you like
    if count >= 7:
        return "High"
    if count >= 3:
        return "Moderate"
    return "Low"
