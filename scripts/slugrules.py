#!/usr/bin/env python3
"""Clover online-ordering slug conventions, derived from observed data.

Validate with: python3 scripts/slugrules.py
"""

import csv
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def base_slug(name, drop_leading_the=False):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower()
    # Apostrophes and periods are deleted, not hyphenated:
    #   "Autumn's Cafe" -> autumns-cafe ; "T.L KITCHEN" -> tl-kitchen
    s = re.sub(r"['’.]", "", s)
    s = re.sub(r"&", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if drop_leading_the and s.startswith("the-"):
        s = s[4:]
    return s


def candidates(name, city_suffix="san-francisco", max_numeric=3):
    """Plausible slugs for a merchant name, most-likely first."""
    out = []
    for drop_the in (False, True):
        b = base_slug(name, drop_the)
        if not b:
            continue
        for form in (f"{b}-{city_suffix}", b):
            if form not in out:
                out.append(form)
            # observed numeric variants: '...-san-francisco8' and '...-san-francisco-2'
            for n in range(2, max_numeric + 1):
                for v in (f"{form}{n}", f"{form}-{n}"):
                    if v not in out:
                        out.append(v)
    return out


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "raw", "nextcard-sf.csv"))))
    rows += list(csv.DictReader(open(os.path.join(ROOT, "data", "raw", "awardhelper-sf.csv"))))
    pairs = [(r["name"], r["slug"]) for r in rows if r["slug"]]
    seen, uniq = set(), []
    for n, s in pairs:
        if s not in seen:
            seen.add(s)
            uniq.append((n, s))

    hit1 = hitn = 0
    misses = []
    for name, slug in uniq:
        cands = candidates(name)
        if cands and cands[0] == slug:
            hit1 += 1
        if slug in cands:
            hitn += 1
        else:
            misses.append((name, slug, cands[0] if cands else ""))

    n = len(uniq)
    print("known (name -> slug) pairs :", n)
    print("first candidate exact      : %d (%.1f%%)" % (hit1, 100.0 * hit1 / n))
    print("slug within candidate set  : %d (%.1f%%)" % (hitn, 100.0 * hitn / n))
    print("\nmisses (%d):" % len(misses))
    for name, slug, guess in misses[:40]:
        print("   %-38s actual=%-45s guess=%s" % (name[:38], slug, guess))


if __name__ == "__main__":
    main()
