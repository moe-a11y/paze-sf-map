#!/usr/bin/env python3
"""
Phase 1 builder for the Paze map project.

Reads ONLY from data/cache/ (never re-requests the network), normalizes each
source into data/raw/<source>-sf.csv, measures pairwise cohesion, then writes
the merged, deduped data/sf-candidates.csv.

Scope: San Francisco plus the northern Peninsula (Daly City through San Mateo /
Burlingame). Selection uses three parallel recall channels -- coordinates,
city+state text, and the Clover slug -- because each one alone misses records
the others catch.

Usage: python3 scripts/build.py
"""

import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402

ROOT = geo.ROOT
CACHE = geo.CACHE
RAW = os.path.join(ROOT, "data", "raw")
NOTES = os.path.join(ROOT, "notes")

# awardhelper's own client-side blocklist (read out of its JS bundle).
AH_BLOCKLIST = {"YY0M35JHFJYQ1", "NA6SRHPVAN6N1", "CCVFP2FRM9MD1",
                "C1625EDB4BNJ1", "BPXVBNQPQH2H1"}

# Subdomains that are shared Clover infrastructure, not a single merchant.
GENERIC_SUBDOMAINS = {"order", "www", "app", "store", "shop", "checkout", "menu"}

OSM_CATEGORY = {
    "restaurant": "restaurants", "cafe": "restaurants", "fast_food": "restaurants",
    "bar": "restaurants", "pub": "restaurants", "ice_cream": "restaurants",
    "food_court": "restaurants", "bakery": "restaurants", "deli": "restaurants",
    "coffee": "restaurants",
    "convenience": "Retail & Services", "greengrocer": "Retail & Services",
    "butcher": "Retail & Services", "seafood": "Retail & Services",
    "alcohol": "Retail & Services", "beverages": "Retail & Services",
    "florist": "Retail & Services", "clothes": "Retail & Services",
    "hairdresser": "Beauty & Wellness", "beauty": "Beauty & Wellness",
}


# ---------------------------------------------------------------- keys

def clover_slug(url):
    """Dedupe key: the merchant subdomain of a *.cloveronline.com URL.

    Returns "" for shared hosts like order.cloveronline.com so those records
    fall through to the fuzzy name+address key instead of colliding.
    """
    if not url:
        return ""
    m = re.search(r"https?://([^./]+)\.cloveronline\.com", url.strip(), re.I)
    if not m:
        return ""
    sub = m.group(1).lower()
    return "" if sub in GENERIC_SUBDOMAINS else sub


def norm_name(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = [w for w in s.split() if w not in
             {"the", "a", "an", "of", "and", "llc", "inc", "co", "restaurant",
              "cafe", "sf", "san", "francisco"}]
    return " ".join(words)


def street_key(addr):
    if not addr:
        return ""
    first = addr.split(",")[0]
    first = unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode().lower()
    first = re.sub(r"[^a-z0-9]+", " ", first).strip()
    return " ".join(first.split()[:3])


def slug_city(slug):
    """Target city named by a slug suffix, or ('', non_target_name)."""
    low = (slug or "").lower().rstrip("0123456789-")
    for city, sufs in geo.CITY_SLUG_SUFFIXES.items():
        for suf in sufs:
            if low.endswith("-" + suf) or low == suf:
                return city, ""
    for bad in geo.NON_TARGET_SLUG_CITIES:
        if low.endswith("-" + bad) or low == bad:
            return "", bad
    return "", ""


# ---------------------------------------------------------------- selection

def select(lat, lon, city, state, slug):
    """Three recall channels. Returns (keep, why, canonical_city)."""
    why = []
    canon = geo.normalize_city(city)
    if geo.in_box(lat, lon):
        why.append("box")
    if canon in geo.TARGET_CITIES and geo.is_ca(state):
        why.append("city")
    sc, _ = slug_city(slug)
    if sc and geo.is_ca(state):
        why.append("slug")
        canon = canon or sc
    return (bool(why), "+".join(why), canon)


def build_row(source, source_id, name, addr, city, state, lat, lon, url,
              category, rating, ordering_status, extra_flags, hoods):
    slug = clover_slug(url)
    keep, why, canon = select(lat, lon, city, state, slug)
    if not keep:
        return None
    lat, lon = float(lat), float(lon)
    hood = geo.sf_neighborhood(lat, lon, hoods)
    if hood in geo.EXCLUDED_NEIGHBORHOODS:
        return None  # Treasure Island / Yerba Buena, per the brief

    flags = list(extra_flags)
    # Area label: SF neighborhood for SF, otherwise the city name.
    if hood:
        area = hood
        if canon and canon != "San Francisco":
            flags.append("coords-in-sf-but-address-says(%s)" % canon)
    elif canon in geo.TARGET_CITIES:
        area = canon
        if "box" not in why and canon not in geo.BOXLESS_CITIES:
            flags.append("coords-outside-area(recovered-by-%s)" % why)
    else:
        area = canon or geo.nearest_city(lat, lon)
        flags.append("outside-target-area(%s)" % (canon or "unknown"))

    if not geo.is_ca(state):
        flags.append("state-mismatch(%s)" % (state or "").strip())
    _, bad = slug_city(slug)
    if bad:
        flags.append("slug-city-mismatch(%s)" % bad)

    return {
        "source": source, "source_id": source_id,
        "name": (name or "").strip(), "address": (addr or "").strip(),
        "city": canon or (city or "").strip(), "neighborhood": area,
        "lat": lat, "lon": lon, "clover_url": url or "", "slug": slug,
        "category": category, "google_rating": rating or "",
        "review_count": "", "ordering_status": ordering_status or "",
        "flags": ";".join(flags),
    }


# ---------------------------------------------------------------- extract

def extract_nextcard(hoods):
    with open(os.path.join(CACHE, "nextcard-snapshot.json")) as fh:
        places = json.load(fh)["places"]
    rows = []
    for p in places:
        ex = p.get("extra") or {}
        url = ex.get("orderingUrl") or ex.get("profileUrl") or ""
        flags = []
        if ex.get("orderingStatus") == "disabled":
            flags.append("nextcard:ordering-disabled")
        cat = ex.get("nonRestaurantCategoryLabel") or p.get("businessType") or ""
        try:
            r = build_row("nextcard", p.get("id", ""), p.get("name"),
                          p.get("streetAddress"), p.get("city"), p.get("state"),
                          p.get("lat"), p.get("lng"), url,
                          cat.replace("_", " "), ex.get("rating"),
                          ex.get("orderingStatus"), flags, hoods)
        except (TypeError, ValueError):
            continue
        if r:
            rows.append(r)
    return rows


def extract_awardhelper(hoods):
    with open(os.path.join(CACHE, "ah-api-raw.json")) as fh:
        recs = json.load(fh)["restaurants"]
    rows = []
    for q in recs:
        flags = []
        if q.get("possibleInactive"):
            flags.append("awardhelper:possible-inactive")
        if q.get("merchantType") == "demo":
            flags.append("awardhelper:demo-merchant")
        if q.get("merchantId") in AH_BLOCKLIST:
            flags.append("awardhelper:site-blocklisted")
        if q.get("pazeConfidence") and q["pazeConfidence"] != "high":
            flags.append("awardhelper:paze-confidence-%s" % q["pazeConfidence"])
        try:
            r = build_row("awardhelper", q.get("merchantId", ""), q.get("name"),
                          q.get("address"), q.get("city"), q.get("state"),
                          q.get("lat"), q.get("lng"), q.get("orderUrl"),
                          "restaurants", None, None, flags, hoods)
        except (TypeError, ValueError):
            continue
        if r:
            rows.append(r)
    return rows


def extract_inferred(hoods):
    """Backfill rows: OSM name -> guessed slug -> DNS hit -> storefront
    confirmed in the target area. Address/coords come from the matched OSM
    POI, not the merchant record, so they are hints rather than facts."""
    hp = os.path.join(CACHE, "dns-hits.json")
    sp = os.path.join(CACHE, "paze-signal.json")
    if not (os.path.exists(hp) and os.path.exists(sp)):
        return []
    hits, sig = json.load(open(hp)), json.load(open(sp))
    rows = []
    for slug, poi in sorted(hits.items()):
        url = "https://%s.cloveronline.com" % slug
        s = sig.get(url) or {}
        city = geo.normalize_city(s.get("page_city") or "")
        if city not in geo.TARGET_CITIES:
            continue  # storefront says it is not in the target area
        lat, lon = float(poi["lat"]), float(poi["lon"])
        hood = geo.sf_neighborhood(lat, lon, hoods)
        flags = ["inferred-not-in-any-map", "address-from-osm-name-match"]
        rows.append({
            "source": "inferred", "source_id": slug,
            "name": s.get("page_name") or poi["name"],
            "address": poi.get("addr", ""), "city": city,
            "neighborhood": hood or city, "lat": lat, "lon": lon,
            "clover_url": url, "slug": slug,
            "category": OSM_CATEGORY.get(poi.get("kind"), "restaurants"),
            "google_rating": "", "review_count": "", "ordering_status": "",
            "flags": ";".join(flags),
        })
    return rows


RAW_COLS = ["source", "source_id", "name", "address", "city", "neighborhood",
            "lat", "lon", "clover_url", "slug", "category", "google_rating",
            "review_count", "ordering_status", "flags"]


def write_raw(rows, fname):
    with open(os.path.join(RAW, fname), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=RAW_COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["name"].lower()):
            w.writerow(r)


# ---------------------------------------------------------------- resolve

def resolve_entities(rows):
    """Union-find on specific slug OR (normalized name, street)."""
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    by_slug, by_fuzzy = {}, {}
    for i, r in enumerate(rows):
        if r["slug"]:
            if r["slug"] in by_slug:
                union(i, by_slug[r["slug"]])
            else:
                by_slug[r["slug"]] = i
        nm, st = norm_name(r["name"]), street_key(r["address"])
        if nm and st:
            fk = (nm, st)
            if fk in by_fuzzy:
                union(i, by_fuzzy[fk])
            else:
                by_fuzzy[fk] = i

    # Third pass: same normalized name within ~60 m is the same merchant even
    # when the slug and the street string both differ. Catches cases like
    # "Taqueria el Gran Amigo" holding two Clover pages at one address whose
    # street text is spelled two ways ("Serramonte" / "Serremonte").
    near = [(i, r, set(norm_name(r["name"]).split())) for i, r in enumerate(rows)]
    for a in range(len(near)):
        ia, ra, ta = near[a]
        if not ta:
            continue
        for b in range(a + 1, len(near)):
            ib, rb, tb = near[b]
            if not tb:
                continue
            # ~60 m in degrees; longitude scaled for this latitude band
            if (abs(ra["lat"] - rb["lat"]) >= 0.00055
                    or abs(ra["lon"] - rb["lon"]) >= 0.00070):
                continue
            # same name, or one name is the other plus a qualifier
            # ("La Lupita Mexican" / "La Lupita Mexican Eatery")
            small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
            if len(small) >= 2 and small <= big:
                union(ia, ib)

    groups = defaultdict(list)
    for i, r in enumerate(rows):
        groups[find(i)].append(r)
    return [groups[k] for k in sorted(groups)]


def cohesion(groups):
    both = [g for g in groups if {r["source"] for r in g} == {"nextcard", "awardhelper"}]
    nco = [g for g in groups if {r["source"] for r in g} == {"nextcard"}]
    aho = [g for g in groups if {r["source"] for r in g} == {"awardhelper"}]
    return {"both": both, "nc_only": nco, "ah_only": aho}


def merge(groups):
    merged = []
    for group in groups:
        base = next((g for g in group if g["source"] == "nextcard"), group[0])
        srcs = sorted({g["source"] for g in group})
        flags = sorted({f for g in group for f in g["flags"].split(";") if f})
        hood = next((g["neighborhood"] for g in group if g["neighborhood"]), "")
        url = (next((g["clover_url"] for g in group if g["slug"]), "")
               or next((g["clover_url"] for g in group if g["clover_url"]), ""))
        rating = next((g["google_rating"] for g in group if g["google_rating"]), "")
        notes = (["single-source(%s)" % srcs[0]] if len(srcs) == 1 else []) + flags
        merged.append({
            "name": base["name"], "address": base["address"],
            "neighborhood": hood, "lat": round(base["lat"], 6),
            "lon": round(base["lon"], 6), "clover_url": url,
            "category": base["category"], "google_rating": rating,
            "review_count": "", "sources": "+".join(srcs),
            "verified": "", "notes": "; ".join(notes),
        })
    return merged


OUT_COLS = ["name", "address", "neighborhood", "lat", "lon", "clover_url",
            "category", "google_rating", "review_count", "sources",
            "verified", "notes"]


def main():
    os.makedirs(RAW, exist_ok=True)
    hoods = geo.load_neighborhoods()

    nc = extract_nextcard(hoods)
    ah = extract_awardhelper(hoods)
    inf = extract_inferred(hoods)
    write_raw(nc, "nextcard-sf.csv")
    write_raw(ah, "awardhelper-sf.csv")
    if inf:
        write_raw(inf, "inferred-sf.csv")

    groups = resolve_entities(nc + ah + inf)
    coh = cohesion(groups)
    merged = merge(groups)

    status_path = os.path.join(CACHE, "url-status.json")
    if os.path.exists(status_path):
        status = json.load(open(status_path))
        lc = Counter()
        for r in merged:
            st = (status.get(r["clover_url"]) or {}).get("status")
            lc[st or "unchecked"] += 1
            if st and st != "live":
                r["notes"] = ("clover-url-dead(%s)" % st) + ("; " + r["notes"] if r["notes"] else "")
        print("url liveness         :", lc.most_common())

    sig_path = os.path.join(CACHE, "paze-signal.json")
    if os.path.exists(sig_path):
        sig = json.load(open(sig_path))
        pz = Counter()
        for r in merged:
            s = sig.get(r["clover_url"])
            if not s:
                pz["unchecked"] += 1
                continue
            sup, flg = s.get("paze_supported"), s.get("paze_flag_enabled")
            if sup is True and flg is True:
                tag, k = "paze-on-storefront=yes", "yes"
            elif sup is False or flg is False:
                tag, k = "paze-on-storefront=NO", "no"
            else:
                tag, k = "paze-on-storefront=unknown", "unknown"
            pz[k] += 1
            r["notes"] = tag + ("; " + r["notes"] if r["notes"] else "")
            city = geo.normalize_city(s.get("page_city") or "")
            if city and city not in geo.TARGET_CITIES:
                r["notes"] += "; storefront-city(%s)" % s["page_city"].strip()
        print("paze storefront sig  :", pz.most_common())

    merged.sort(key=lambda r: r["name"].lower())
    with open(os.path.join(ROOT, "data", "sf-candidates.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS)
        w.writeheader()
        w.writerows(merged)

    nb, nn, na = len(coh["both"]), len(coh["nc_only"]), len(coh["ah_only"])
    tot = nb + nn + na
    print("nextcard rows        :", len(nc))
    print("awardhelper rows     :", len(ah))
    print("inferred rows        :", len(inf))
    print("resolved entities    :", tot, "(+%d inferred-only)" % len(inf))
    print("  both / nc / ah     : %d / %d / %d  (both = %.1f%%)" % (nb, nn, na, 100.0 * nb / tot))
    print("MERGED TOTAL         :", len(merged))
    print("by city/area         :")
    for k, v in Counter(r["neighborhood"] for r in merged).most_common(20):
        print("   %-28s %d" % (k, v))


if __name__ == "__main__":
    main()
