#!/usr/bin/env python3
"""
Read the Paze support signal off each Clover storefront's page root.

The storefront root embeds its own payment config, e.g.

    "paze":{"supported":true,"client_id":"..."}
    "launchDarklyFeatures":[{"name":"PAZE_ON_COLO2","enabled":true}, ...]

and its city in the meta description ("Based in SAN FRANCISCO.").

That means Paze availability is readable WITHOUT touching the checkout flow.
Only the page root is requested -- which each merchant's robots.txt explicitly
allows, and which is the same thing a browser loads before you add anything to
a cart. Nothing under /checkout/, /confirmation/ or /customer-profile/ is ever
requested, and no cart is created. 1 request/second.

Usage:
    python3 scripts/paze_signal.py                 # all live candidates
    python3 scripts/paze_signal.py <url> [<url>…]  # specific URLs

Writes data/cache/paze-signal.json.
"""

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cache")
OUT = os.path.join(CACHE, "paze-signal.json")
UA = ("PazeSFMapBot/0.1 (personal research project; "
      "contact tylerjackson117@protonmail.com)")

RE_PAZE_SUPPORTED = re.compile(r'\\?"paze\\?"\s*:\s*\{\s*\\?"supported\\?"\s*:\s*(true|false)', re.I)
RE_PAZE_FLAG = re.compile(r'\\?"name\\?"\s*:\s*\\?"PAZE_ON_COLO2\\?"\s*,\s*\\?"enabled\\?"\s*:\s*(true|false)', re.I)
RE_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
RE_DESC = re.compile(r'<meta\s+name="description"\s+content="(.*?)"', re.I | re.S)
RE_BASED_IN = re.compile(r"Based in ([^.\"<]+)", re.I)
RE_APPLE = re.compile(r'\\?"apple_pay\\?"\s*:\s*\{\s*\\?"supported\\?"\s*:\s*(true|false)', re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def parse(html):
    def b(m):
        return None if not m else (m.group(1).lower() == "true")
    title = RE_TITLE.search(html)
    desc = RE_DESC.search(html)
    based = RE_BASED_IN.search(desc.group(1)) if desc else None
    return {
        "paze_supported": b(RE_PAZE_SUPPORTED.search(html)),
        "paze_flag_enabled": b(RE_PAZE_FLAG.search(html)),
        "apple_pay": b(RE_APPLE.search(html)),
        "page_name": title.group(1).strip() if title else "",
        "page_city": based.group(1).strip() if based else "",
        "mentions_paze": html.lower().count("paze"),
    }


def main():
    urls = sys.argv[1:]
    if not urls:
        status = json.load(open(os.path.join(CACHE, "url-status.json")))
        rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "sf-candidates.csv"))))
        urls = [r["clover_url"] for r in rows
                if status.get(r["clover_url"], {}).get("status") == "live"]
    urls = sorted(set(urls))

    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [u for u in urls if u not in out]
    print("%d URLs, %d already cached, %d to fetch (~%d min)"
          % (len(urls), len(urls) - len(todo), len(todo), len(todo) // 60 + 1))

    for i, u in enumerate(todo, 1):
        try:
            code, html = fetch(u)
            rec = parse(html)
            rec["http"] = code
        except urllib.error.HTTPError as e:
            rec = {"http": e.code, "error": "HTTPError"}
        except Exception as e:
            rec = {"http": 0, "error": type(e).__name__ + ": " + str(e)[:150]}
        out[u] = rec
        print("[%3d/%d] paze=%-5s flag=%-5s city=%-18s %s"
              % (i, len(todo), rec.get("paze_supported"), rec.get("paze_flag_enabled"),
                 (rec.get("page_city") or "")[:18], u.replace("https://", "")), flush=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        time.sleep(1)
    print("\ndone ->", OUT)


if __name__ == "__main__":
    main()
