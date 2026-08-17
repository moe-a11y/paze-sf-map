# Paze map — San Francisco + northern Peninsula

A personal tool for the Paze promo (spend $10+ via Paze checkout, get $10 back;
up to 10 redemptions per card, $100 max). **Promo ends 2026-09-10.**

**[Open the map →](map.html)** (needs HTTPS for geolocation — GitHub Pages
serves it; `file://` will not give you your location)

## What's here

| Path | What it is |
|---|---|
| `map.html` | The map. Single file, Leaflet + CARTO tiles, no build step, no API key. |
| `data/sf-candidates.csv` | 211 candidate merchants, deduped, with provenance and caveat flags. |
| `data/starred.json` | The shortlist, keyed by Clover URL. Edit and re-run `make_map.py`. |
| `data/raw/*.csv` | Per-source extracts before merging — kept separate so cohesion is measurable. |
| `notes/sources.md` | Where every dataset came from, what was declined and why. |
| `notes/cohesion.md` | Whether the community maps are one dataset or several. |
| `scripts/` | The pipeline. |

## Rebuilding

`data/cache/` is gitignored (47 MB of upstream payloads, regenerable, and not
ours to redistribute). Re-fetch per `notes/sources.md`, then:

```sh
python3 scripts/build.py        # cache -> data/raw/*.csv -> sf-candidates.csv
python3 scripts/verify_urls.py  # liveness check, 1 req/sec
python3 scripts/paze_signal.py  # reads Paze support off each storefront root
python3 scripts/make_map.py     # regenerates map.html (keeps your redemption log)
```

`scripts/backfill_probe.py` is the optional recall pass: OSM names → predicted
Clover slugs → DNS. Slow (~18k lookups) and low-yield, but it finds merchants
neither community map lists.

## Ground rules this followed

- `robots.txt` checked for every domain before fetching. `pazemap.com`
  disallows this agent and was **not** scraped.
- One bulk fetch per source, cached to disk; all later builds read the cache.
- ≤1 request/second, self-identifying User-Agent.
- **No checkout flow was ever touched.** Paze support is read from the
  storefront page root, which merchant `robots.txt` explicitly allows while
  disallowing `/checkout/`. No carts were created.

## Known gaps

- `review_count` is empty — no source carries it and Google Places needs a
  billing-attached key.
- `pazemap.com` is unmeasured, so cohesion is a two-source comparison.
- The "OFF" badge (ordering disabled) comes from nextcard's 2026-08-07
  snapshot and could not be confirmed live. Treat it as a hint.
- Backfill recall is poor by construction: slug prediction reproduces only
  ~65% of *known* slugs, so its finds are a floor, not a ceiling.
