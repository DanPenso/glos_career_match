"""Approximate commute hints for Gloucestershire / Bristol match reports.

Not live routing — centroids and typical road speed only, so copy stays stable
without calling a maps API.
"""

from __future__ import annotations

import math
import re
from typing import Any

# lat, lon, display label, National Rail station name (empty if none nearby).
_PLACES: dict[str, dict[str, Any]] = {
    "cheltenham": {
        "label": "Cheltenham",
        "lat": 51.899,
        "lon": -2.078,
        "station": "Cheltenham Spa",
    },
    "gloucester": {
        "label": "Gloucester",
        "lat": 51.864,
        "lon": -2.244,
        "station": "Gloucester",
    },
    "stroud": {"label": "Stroud", "lat": 51.746, "lon": -2.216, "station": "Stroud"},
    "stonehouse": {
        "label": "Stonehouse",
        "lat": 51.747,
        "lon": -2.284,
        "station": "Stonehouse",
    },
    "cirencester": {
        "label": "Cirencester",
        "lat": 51.719,
        "lon": -1.968,
        "station": "Kemble",
    },
    "tewkesbury": {
        "label": "Tewkesbury",
        "lat": 51.993,
        "lon": -2.156,
        "station": "Ashchurch for Tewkesbury",
    },
    "cinderford": {
        "label": "the Forest of Dean",
        "lat": 51.824,
        "lon": -2.499,
        "station": "Lydney",
    },
    "lydney": {"label": "Lydney", "lat": 51.726, "lon": -2.530, "station": "Lydney"},
    "bristol": {
        "label": "Bristol",
        "lat": 51.4545,
        "lon": -2.5879,
        "station": "Bristol Temple Meads",
    },
    "filton": {
        "label": "Filton",
        "lat": 51.510,
        "lon": -2.576,
        "station": "Filton Abbey Wood",
    },
    "yate": {"label": "Yate", "lat": 51.541, "lon": -2.414, "station": "Yate"},
    "thornbury": {"label": "Thornbury", "lat": 51.609, "lon": -2.525, "station": ""},
    "dursley": {
        "label": "Dursley",
        "lat": 51.681,
        "lon": -2.354,
        "station": "Cam & Dursley",
    },
    "wotton-under-edge": {
        "label": "Wotton-under-Edge",
        "lat": 51.638,
        "lon": -2.353,
        "station": "Cam & Dursley",
    },
    "nailsworth": {"label": "Nailsworth", "lat": 51.695, "lon": -2.219, "station": ""},
    "tetbury": {"label": "Tetbury", "lat": 51.639, "lon": -2.158, "station": ""},
    "cam": {
        "label": "Cam",
        "lat": 51.698,
        "lon": -2.367,
        "station": "Cam & Dursley",
    },
    "berkeley": {"label": "Berkeley", "lat": 51.691, "lon": -2.459, "station": ""},
    "newent": {"label": "Newent", "lat": 51.930, "lon": -2.405, "station": ""},
    "coleford": {
        "label": "Coleford",
        "lat": 51.794,
        "lon": -2.616,
        "station": "Lydney",
    },
}

_INTAKE_ALIAS = {
    "cheltenham": "cheltenham",
    "gloucester": "gloucester",
    "stroud": "stroud",
    "cirencester / cotswolds": "cirencester",
    "cirencester": "cirencester",
    "cotswolds": "cirencester",
    "tewkesbury / north gloucestershire": "tewkesbury",
    "tewkesbury": "tewkesbury",
    "forest of dean": "cinderford",
    "bristol": "bristol",
    "south gloucestershire / filton": "filton",
    "filton": "filton",
    "south gloucestershire": "filton",
    "willing to commute / hybrid / bristol": "bristol",
}

_COUNTYWIDE = {
    "anywhere in gloucestershire",
    "anywhere",
}

# Straight-line miles → typical road minutes in this county (matches Cheltenham–Stonehouse ≈ 40).
_ROAD_FACTOR = 1.35
_MPH = 28.0


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _resolve_place(text: str) -> str | None:
    raw = _norm(text)
    if not raw:
        return None
    if raw in _INTAKE_ALIAS:
        return _INTAKE_ALIAS[raw]
    if raw in _PLACES:
        return raw
    compact = raw.replace(" ", "-")
    if compact in _PLACES:
        return compact
    for key, meta in _PLACES.items():
        label = _norm(str(meta.get("label") or ""))
        if key in raw.split() or key.replace("-", " ") in raw or (label and label in raw):
            return key
    if "corridor" in raw and "gloucester" in raw:
        return "gloucester"
    if "corridor" in raw and "cheltenham" in raw:
        return "cheltenham"
    return None


def _haversine_miles(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1 = math.radians(float(a["lat"])), math.radians(float(a["lon"]))
    lat2, lon2 = math.radians(float(b["lat"])), math.radians(float(b["lon"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 3958.8 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _drive_minutes(origin: dict[str, Any], dest: dict[str, Any]) -> int:
    miles = _haversine_miles(origin, dest) * _ROAD_FACTOR
    minutes = miles / _MPH * 60.0
    rounded = int(round(minutes / 5.0) * 5)
    return max(10, min(90, rounded))


def commute_hint(origin_text: Any, dest_text: Any) -> str:
    """One sentence on drive time and trains, or empty if we cannot say."""
    origin_raw = str(origin_text or "").strip()
    dest_raw = str(dest_text or "").strip()
    if not origin_raw or not dest_raw:
        return ""
    if _norm(origin_raw) in _COUNTYWIDE:
        dest = _resolve_place(dest_raw)
        dest_meta = _PLACES.get(dest or "")
        if not dest_meta:
            return ""
        station = str(dest_meta.get("station") or "").strip()
        if station:
            return (
                f"{dest_meta['label']} is in Gloucestershire, with road links from "
                f"Cheltenham, Gloucester, and Stroud, and trains at {station}."
            )
        return (
            f"{dest_meta['label']} is in Gloucestershire, with road links from "
            "Cheltenham, Gloucester, and Stroud."
        )
    origin_key = _resolve_place(origin_raw)
    dest_key = _resolve_place(dest_raw)
    if not origin_key or not dest_key:
        return ""
    origin = _PLACES[origin_key]
    dest = _PLACES[dest_key]
    if origin_key == dest_key:
        return f"That's in {origin['label']} with you, so travel is local."
    minutes = _drive_minutes(origin, dest)
    drive = (
        f"{dest['label']} is about a {minutes} minute drive from your location "
        f"in {origin['label']}"
    )
    origin_st = str(origin.get("station") or "").strip()
    dest_st = str(dest.get("station") or "").strip()
    if origin_st and dest_st and origin_st != dest_st:
        return f"{drive}, or there are regular trains from {origin_st} to {dest_st}."
    if origin_st:
        return f"{drive}, or there are regular trains from {origin_st}."
    return f"{drive}."
