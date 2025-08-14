import json, os, time, hashlib
from flask import current_app

def _cache_dir():
    d = os.path.join(current_app.instance_path, "cache")
    os.makedirs(d, exist_ok=True)
    return d

def _path(key: str):
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(_cache_dir(), f"{h}.json")

def get(key: str, ttl_seconds: int = 3600):
    p = _path(key)
    if not os.path.exists(p): return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            blob = json.load(f)
        if time.time() - blob.get("_ts", 0) > ttl_seconds:
            return None
        return blob.get("data")
    except Exception:
        return None

def put(key: str, data):
    p = _path(key)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"_ts": time.time(), "data": data}, f)
