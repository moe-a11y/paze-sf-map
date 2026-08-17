#!/usr/bin/env python3
"""Shared geography for the Paze project: target area, city normalization,
SF neighborhood polygons, and nearest-city assignment."""

import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")

# Expanded target area: San Francisco plus the northern Peninsula, per the
# follow-up scope (Daly City / San Mateo / Burlingame and everything between).
# Original SF-only box from the brief was 37.70-37.84 / -122.52 to -122.35.
BOX = (37.50, 37.84, -122.56, -122.28)

# Explicitly excluded per the brief.
EXCLUDED_NEIGHBORHOODS = {"Treasure Island", "Yerba Buena Island"}

# Canonical target cities. Belmont and San Carlos sit just past San Mateo but
# are inside the box; they are kept and labelled so they can be filtered out.
TARGET_CITIES = {
    "San Francisco", "Daly City", "Colma", "Brisbane", "South San Francisco",
    "San Bruno", "Millbrae", "Burlingame", "Hillsborough", "San Mateo",
    "Foster City", "Pacifica", "Broadmoor", "Belmont", "San Carlos",
}

# Spelling variants seen in the feeds -> canonical name.
CITY_ALIASES = {
    "sf": "San Francisco", "s f": "San Francisco",
    "san francisco ca": "San Francisco", "san-francisco": "San Francisco",
    "san-francisco-ca": "San Francisco", "sanfrancisco": "San Francisco",
    "s san fran": "South San Francisco", "s san francisco": "South San Francisco",
    "so san francisco": "South San Francisco", "south sf": "South San Francisco",
    "s. san francisco": "South San Francisco", "ssf": "South San Francisco",
    # storefront meta descriptions truncate long city names
    "south san francisc": "South San Francisco", "s san francis": "South San Francisco",
    "s san franci": "South San Francisco",
    "milbrae": "Millbrae", "daly-city": "Daly City",
}

# Approximate city centres, for labelling POIs that carry no addr:city.
CITY_CENTRES = [
    ("San Francisco", 37.7749, -122.4194),
    ("Daly City", 37.6879, -122.4702),
    ("Colma", 37.6769, -122.4597),
    ("Brisbane", 37.6808, -122.3999),
    ("South San Francisco", 37.6547, -122.4077),
    ("San Bruno", 37.6305, -122.4111),
    ("Millbrae", 37.5985, -122.3872),
    ("Burlingame", 37.5841, -122.3661),
    ("Hillsborough", 37.5741, -122.3794),
    ("San Mateo", 37.5630, -122.3255),
    ("Foster City", 37.5585, -122.2711),
    ("Pacifica", 37.6138, -122.4869),
    ("Belmont", 37.5202, -122.2758),
    ("San Carlos", 37.5072, -122.2605),
]

# Clover slug suffixes for each target city, most common form first.
CITY_SLUG_SUFFIXES = {
    "San Francisco": ["san-francisco", "sf"],
    "Daly City": ["daly-city"],
    "Colma": ["colma"],
    "Brisbane": ["brisbane"],
    "South San Francisco": ["south-san-francisco", "s-san-francisco", "ssf"],
    "San Bruno": ["san-bruno"],
    "Millbrae": ["millbrae"],
    "Burlingame": ["burlingame"],
    "Hillsborough": ["hillsborough"],
    "San Mateo": ["san-mateo"],
    "Foster City": ["foster-city"],
    "Pacifica": ["pacifica"],
    "Belmont": ["belmont"],
    "San Carlos": ["san-carlos"],
}

# Slug suffixes that name a city OUTSIDE the target area.
NON_TARGET_SLUG_CITIES = (
    "portland", "riverside", "vallejo", "sacramento", "redding", "oakland",
    "san-jose", "berkeley", "los-angeles", "san-diego", "fresno", "stockton",
    "modesto", "hayward", "fremont", "elk-grove", "durham", "nicasio",
)


def normalize_city(city):
    if not city:
        return ""
    c = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode()
    c = re.sub(r"\s+", " ", c.strip())
    low = c.lower().rstrip(".,")
    if low in CITY_ALIASES:
        return CITY_ALIASES[low]
    title = low.title()
    return title if title in TARGET_CITIES else c


def is_ca(state):
    return (state or "").strip().upper() in ("CA", "CALIFORNIA", "")


def in_box(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return BOX[0] <= lat <= BOX[1] and BOX[2] <= lon <= BOX[3]


def nearest_city(lat, lon):
    best, bd = "", 1e9
    for name, la, lo in CITY_CENTRES:
        d = (lat - la) ** 2 + (lon - lo) ** 2
        if d < bd:
            best, bd = name, d
    return best


# ------------------------------------------------------------- polygons

def load_neighborhoods():
    with open(os.path.join(CACHE, "sf-neighborhoods.geojson")) as fh:
        gj = json.load(fh)
    hoods = []
    for feat in gj["features"]:
        name = feat["properties"]["name"]
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        rings = [[[(float(x), float(y)) for x, y in ring] for ring in poly] for poly in polys]
        xs = [x for poly in rings for ring in poly for x, y in ring]
        ys = [y for poly in rings for ring in poly for x, y in ring]
        hoods.append((name, rings, min(xs), max(xs), min(ys), max(ys)))
    return hoods


def _in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def sf_neighborhood(lat, lon, hoods):
    """SF neighborhood name, or None if the point is not in SF proper."""
    for name, rings, x0, x1, y0, y1 in hoods:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in rings:
            if _in_ring(lon, lat, poly[0]) and not any(
                    _in_ring(lon, lat, hole) for hole in poly[1:]):
                return name
    return None
