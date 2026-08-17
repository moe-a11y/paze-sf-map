#!/usr/bin/env python3
"""
Generate map.html -- a single self-contained page with the merchant list baked
in as an editable JSON blob.

Regenerate any time the CSV changes:  python3 scripts/make_map.py

Hand-edits to the REDEMPTIONS blob inside map.html are preserved on regenerate
(the block between the REDEMPTIONS markers is carried over if present).
"""

import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "map.html")

PROMO_END = "2026-09-10"

DEFAULT_REDEMPTIONS = """{
  "maxPerCard": 10,
  "maxCreditPerCard": 100,
  "cards": {
    "Card 1": [],
    "Card 2": []
  }
}"""


def load():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "sf-candidates.csv"))))
    starred_urls = set()
    sp = os.path.join(ROOT, "data", "starred.json")
    if os.path.exists(sp):
        for urls in json.load(open(sp)).values():
            starred_urls.update(urls)

    out = []
    for r in rows:
        notes = r["notes"]
        if "clover-url-dead" in notes:
            status = "dead"
        elif "ordering-disabled" in notes:
            status = "disabled"
        else:
            status = "ok"
        warn = []
        if "outside-target-area" in notes or "storefront-city" in notes:
            warn.append("location unconfirmed")
        if "address-from-osm" in notes:
            warn.append("address approximate")
        if "paze-on-storefront=yes" in notes:
            paze = "yes"
        elif "paze-on-storefront=NO" in notes:
            paze = "no"
        else:
            paze = "unchecked"
        out.append({
            "n": r["name"],
            "a": r["address"],
            "h": r["neighborhood"],
            "y": float(r["lat"]),
            "x": float(r["lon"]),
            "u": r["clover_url"],
            "c": r["category"],
            "s": 1 if r["clover_url"] in starred_urls else 0,
            "st": status,
            "p": paze,
            "w": warn,
        })
    out.sort(key=lambda m: (-m["s"], m["n"].lower()))
    return out


def carry_over_redemptions():
    if not os.path.exists(OUT):
        return DEFAULT_REDEMPTIONS
    txt = open(OUT).read()
    m = re.search(r"/\* REDEMPTIONS-START \*/\s*(.*?)\s*/\* REDEMPTIONS-END \*/", txt, re.S)
    if not m:
        return DEFAULT_REDEMPTIONS
    body = m.group(1)
    body = re.sub(r"^const\s+REDEMPTIONS\s*=\s*", "", body).rstrip(";").strip()
    return body


TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "map_template.html")


def main():
    merchants = load()
    html = (open(TEMPLATE).read()
            .replace("__MERCHANTS__", json.dumps(merchants, separators=(",", ":")))
            .replace("__REDEMPTIONS__", carry_over_redemptions())
            .replace("__PROMO_END__", PROMO_END))
    with open(OUT, "w") as fh:
        fh.write(html)
    stars = sum(1 for m in merchants if m["s"])
    dead = sum(1 for m in merchants if m["st"] == "dead")
    dis = sum(1 for m in merchants if m["st"] == "disabled")
    print("wrote %s  (%.0f KB)" % (OUT, os.path.getsize(OUT) / 1024))
    print("  merchants %d | starred %d | dead %d | ordering-off %d"
          % (len(merchants), stars, dead, dis))


if __name__ == "__main__":
    main()
