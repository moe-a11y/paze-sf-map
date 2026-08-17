# Project Brief: Personal Paze Map for San Francisco

## Context

Paze (digital wallet from Early Warning Services, the Zelle company) is running a promo through **September 10, 2026**: spend $10+ in a single transaction using Paze checkout, get a $10 statement credit. Up to 10 redemptions per card, $100 max per card. Multiple cards each qualify separately.

The largest pool of eligible merchants is not on Paze's official directory (~34 national brands). It's the long tail of independent businesses running **Clover** online ordering. When a Clover merchant has an online ordering page — usually at `<merchant-slug>.cloveronline.com` — Paze shows up as a checkout option.

Three community sites have mapped this. None are affiliated with Clover or Paze:

| Site | Claimed coverage | Notes |
|---|---|---|
| `nextcard.com/tools/clover-paze-map` | ~35,500 | Largest; only one claiming non-restaurant merchants |
| `awardhelper.com/paze-restaurants` | ~28,000 | The one Doctor of Credit links first |
| `pazemap.com` | unstated | Bilingual EN/中文; has rating + gift-card filters |

A fourth, MealMaxxer, cross-references Clover against Bilt/Resy/inKind. A site called `pazemaps.com` (plural) may also exist but blocks automated access and isn't indexed — treat as unverified.

**Open question this project needs to answer:** are these three maps drawing from one cohesive upstream source (Clover's own public data), or are they independently assembled with different gaps? The answer determines whether we can trust any one of them or need to union them and backfill.

## Goal

Two phases, with a human checkpoint between them.

**Phase 1 (now):** Produce a complete, deduplicated CSV of every Clover online-ordering merchant in San Francisco that plausibly accepts Paze. Optimize for *recall* — I would rather review 400 rows and discard 350 than miss a place I'd actually go.

**Phase 2 (after I manually pick my shortlist):** Build a single-file HTML map I can open on my phone or laptop that shows my current location plus my selected merchants nearby.

---

## Phase 1: Build the candidate list

### Ground rules

- **Check `robots.txt` and terms of service for every domain before fetching.** If a site disallows automated access, don't scrape it — note it as a manual-review source instead and move on.
- **Prefer one bulk fetch over many.** These maps are client-side apps that almost certainly load merchant data from a single JSON or similar endpoint. Find that file by reading the page's JS bundle, fetch it once, and cache it to disk. Never re-request during development — work off the local cache.
- **Rate-limit anything that must be crawled.** 1 request/second ceiling, identify yourself in the User-Agent.
- **Do not automate anything past a merchant's "add to cart" step.** Probing real checkout flows to detect the Paze button means generating fake carts against small businesses' payment systems, and it will get us blocked besides. Checkout verification stays manual — see the `verified` column below.

### Steps

1. **Source assessment.** For each of the three maps, determine: what URL serves its merchant data, what fields it exposes, and when it was last updated. Write findings to `notes/sources.md` before extracting anything.

2. **Extract to a common schema.** Normalize each source into its own CSV under `data/raw/`. Don't merge yet — keeping them separate is what makes step 3 possible.

3. **Measure cohesion.** This directly answers the open question above. Compute pairwise overlap between the three sets restricted to SF: how many merchants appear in all three, in exactly two, in exactly one. Report as a short table in `notes/cohesion.md`.
   - High overlap (>90% three-way) → they share an upstream source; pick the richest one and move on.
   - Low overlap → they're independently assembled and each has gaps. Union everything and proceed to step 5.

4. **Merge and dedupe.** Union all three into `data/sf-candidates.csv`. Dedupe on normalized `cloveronline` URL slug first (most reliable key), then fall back to fuzzy name + address match. Keep a `sources` column listing which maps each merchant came from — a merchant appearing in only one source is more likely to be stale or a false positive.

5. **Backfill gaps (only if step 3 showed low cohesion).** Two approaches, in order of preference:
   - Find Clover's own public merchant/online-ordering directory and query it directly for SF. This is the actual upstream source and would supersede all three maps.
   - Failing that: pull SF restaurants from a places API, then test each candidate for the existence of a `cloveronline.com` ordering page. Flag these as `source=inferred` since they're unconfirmed.

6. **Geographic filter.** SF proper only. Bounding box roughly lat `37.70`–`37.84`, lon `-122.52`–`-122.35`. Exclude Treasure Island and the Farallones. Tag each row with its neighborhood — I'll be filtering heavily on this.

7. **Enrich for triage.** Add Google rating and review count to each row if you can do it within API free tiers. Review *count* matters more than rating for my purposes: it separates established neighborhood places from one-off delis with four five-star reviews.

### Output schema

`data/sf-candidates.csv`:

```
name, address, neighborhood, lat, lon, clover_url, category,
google_rating, review_count, sources, verified, notes
```

Leave `verified` blank — I'll fill it in manually. Sort by `review_count` descending so the recognizable places surface first.

### Definition of done for Phase 1

- `data/sf-candidates.csv` exists, deduped, every row has a working `clover_url`
- `notes/cohesion.md` answers whether the three maps are cohesive
- `notes/sources.md` documents where each dataset came from and any site we declined to scrape
- A one-paragraph summary in chat: total candidates, how many from all three sources vs. one, and your confidence in coverage

**Stop here and wait for me.** I'll go through the CSV by hand, set `verified` on the ones I've confirmed show the Paze button at checkout, and hand you back a filtered file.

---

## Phase 2: The map (after my manual pass)

Build `map.html` — a **single self-contained file**, no build step.

**Requirements:**
- Leaflet + OpenStreetMap tiles. No API key, no billing account.
- Browser Geolocation API for my position, with a graceful fallback to a default SF center if I decline the permission prompt.
- My selected merchants as pins, sorted by distance from me. Tapping a pin shows name, neighborhood, distance, and a direct link to the Clover ordering page.
- A visible counter of how many redemptions I have left. Merchant data and my redemption log both live in a JSON blob inside the file — I'll hand-edit it. No backend, no database.
- Mobile-first layout. I'll be using this one-handed while walking.

**Two gotchas to design around:**
- Geolocation requires a secure context. Chrome blocks it over `file://`. So either serve locally (`python -m http.server`) or push to GitHub Pages. Tell me which you've set it up for.
- The promo ends September 10, 2026. Show days remaining somewhere visible.

---

## What I care about

Recall over precision in Phase 1. Honest reporting on coverage gaps — if the data is thin or stale, say so rather than papering over it. And don't over-build Phase 2; it's a static map for one person for three weeks, not a product.
