#!/usr/bin/env python3
"""
Step 5 backfill: infer Clover online-ordering pages for SF businesses that
neither community map lists.

Method: OpenStreetMap POI names (free, keyless) -> candidate Clover slugs ->
DNS resolution. cloveronline.com has NO wildcard DNS (verified: nonsense
subdomains return NXDOMAIN), so a successful lookup is strong evidence the
ordering page really exists.

DNS only -- this generates zero HTTP traffic against merchant storefronts.
Confirmation of the hits happens separately in backfill_confirm.py.

Writes data/cache/dns-hits.json.
"""

import csv
import json
import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slugrules import base_slug  # noqa: E402
import geo  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
OUT = os.path.join(CACHE, "dns-hits.json")
WORKERS = 16


def known_slugs():
    known = set()
    for f in ("nextcard-sf.csv", "awardhelper-sf.csv"):
        p = os.path.join(ROOT, "data", "raw", f)
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                if r["slug"]:
                    known.add(r["slug"])
    return known


def probe_forms(name, city="San Francisco"):
    """Highest-yield slug shapes for a merchant name in a given city,
    per scripts/slugrules.py."""
    forms = []
    b = base_slug(name)
    bt = base_slug(name, drop_leading_the=True)
    sufs = geo.CITY_SLUG_SUFFIXES.get(city, ["san-francisco"])
    cands = []
    for suf in sufs:
        cands += [f"{b}-{suf}", f"{bt}-{suf}"]
    cands += [b, bt, f"{b}sf"]
    for x in cands:
        # bare forms are only safe for distinctive names -- 'deli' alone
        # would collide with an unrelated merchant in another city
        ok = len(x) >= 12 if not any(x.endswith("-" + s) for s in sufs) else len(x) > 6
        if ok and x not in forms:
            forms.append(x)
    return forms


def resolve(slug):
    host = slug + ".cloveronline.com"
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return slug
    except socket.gaierror:
        return None
    except Exception:
        return None


def main():
    els = []
    for f in ("osm-sf-poi.json", "osm-peninsula-poi.json"):
        p = os.path.join(CACHE, f)
        if os.path.exists(p):
            els += json.load(open(p))["elements"]

    pois = {}
    for e in els:
        t = e.get("tags") or {}
        nm = (t.get("name") or "").strip()
        if not nm:
            continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat")
        lon = e.get("lon") or (e.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        # City drives which slug suffix to try; OSM's addr:city when present,
        # otherwise the nearest city centre.
        city = geo.normalize_city(t.get("addr:city") or "")
        if city not in geo.TARGET_CITIES:
            city = geo.nearest_city(float(lat), float(lon))
        pois.setdefault((nm, city), {
            "name": nm, "lat": lat, "lon": lon, "city": city,
            "kind": t.get("amenity") or t.get("shop") or "",
            "addr": " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x),
        })
    print("distinct (name, city) POIs:", len(pois))

    known = known_slugs()
    print("already-known slugs:", len(known))

    todo = {}          # slug -> poi key
    for key, p in pois.items():
        for s in probe_forms(p["name"], p["city"]):
            if s in known or s in todo:
                continue
            todo[s] = key
    print("candidate slugs to resolve:", len(todo))

    hits = {}
    done = 0
    slugs = list(todo)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(resolve, slugs):
            done += 1
            if res:
                hits[res] = pois[todo[res]]
                print("  HIT %-55s <- %s" % (res, todo[res]), flush=True)
            if done % 2000 == 0:
                print("  ...%d/%d resolved, %d hits" % (done, len(slugs), len(hits)), flush=True)

    print("\nTOTAL DNS HITS: %d (from %d probes)" % (len(hits), len(slugs)))
    if os.path.exists(OUT):          # never lose previously confirmed hits
        prev = json.load(open(OUT))
        prev.update(hits)
        hits = prev
        print("merged with prior hits -> %d total" % len(hits))
    with open(OUT, "w") as fh:
        json.dump(hits, fh, indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
