#!/usr/bin/env python3
"""
Liveness-check every clover_url in data/sf-candidates.csv.

Only requests the merchant page root, which each merchant subdomain's
robots.txt explicitly allows. Never touches /checkout/ (robots-disallowed,
and out of bounds per the project brief). 1 request/second.

Writes data/cache/url-status.json.
"""

import csv
import json
import os
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("PazeSFMapBot/0.1 (personal research project; "
      "contact tylerjackson117@protonmail.com)")
OUT = os.path.join(ROOT, "data", "cache", "url-status.json")


def check(url):
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Encoding": "identity",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(60000).decode("utf-8", "ignore")
            return {"code": resp.status, "final": resp.geturl(),
                    "len": len(body), "body_head": body[:4000]}
    except urllib.error.HTTPError as e:
        return {"code": e.code, "final": url, "len": 0, "body_head": ""}
    except Exception as e:  # DNS failure, TLS error, timeout
        return {"code": 0, "final": url, "len": 0,
                "body_head": "", "error": type(e).__name__ + ": " + str(e)[:200]}


def classify(res):
    """Distinguish a live storefront from a parked/dead Clover page."""
    if res["code"] == 0:
        return "unreachable"
    if res["code"] == 404:
        return "not-found"
    if res["code"] >= 500:
        return "server-error"
    if res["code"] >= 400:
        return "http-%d" % res["code"]
    head = res.get("body_head", "").lower()
    final = res.get("final", "").lower()
    if "/not-found" in final or "/expired" in final:
        return "expired-or-missing"
    for needle in ("no longer accepting online orders",
                   "store is currently unavailable",
                   "page not found",
                   "this store is closed permanently"):
        if needle in head:
            return "closed"
    return "live"


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "sf-candidates.csv"))))
    urls = sorted({r["clover_url"] for r in rows if r["clover_url"]})
    print("checking %d unique URLs at 1 req/sec (~%d min)" % (len(urls), len(urls) // 60 + 1))
    out = {}
    if os.path.exists(OUT):  # resume support
        out = json.load(open(OUT))
    for i, u in enumerate(urls, 1):
        if u in out:
            continue
        res = check(u)
        res["status"] = classify(res)
        res.pop("body_head", None)
        out[u] = res
        print("[%3d/%d] %-14s %s" % (i, len(urls), res["status"], u), flush=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        time.sleep(1)
    print("\ndone ->", OUT)


if __name__ == "__main__":
    main()
