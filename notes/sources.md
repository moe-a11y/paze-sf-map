# Source assessment

All fetches were made with `User-Agent: PazeSFMapBot/0.1 (personal research
project; contact tylerjackson117@protonmail.com)`, rate-limited to ≤1 req/sec,
and cached to `data/cache/`. Every build after the first read from that cache
only. No checkout flow was touched on any merchant site.

Assessment date: **2026-08-16**.

**Scope:** San Francisco plus the northern Peninsula (Daly City through San
Mateo / Burlingame / San Carlos). 212 merchants. Selection uses three parallel
recall channels — coordinates, city+state text, and Clover slug — since
coordinate-only filtering drops wrongly-geocoded records.

---

## 1. nextcard.com — USED (primary)

| | |
|---|---|
| Page | `https://www.nextcard.com/tools/clover-paze-map` |
| robots.txt | `Allow: /`; the disallow list covers `/index*.html`, `/home`, `/wallet`, `/admin`, `/notifications`, `/personalized-recs`, `/recommendations`, `/auto-bonus`, `/reminders`. **`/tools/*` is not restricted.** |
| Data endpoint | `https://nextcard-static.s3.us-east-1.amazonaws.com/discovery-map-tiles/clover-paze-map/restaurants/snapshots/sha256-0048d491…/snapshot.json` |
| How found | The page HTML references `…/restaurants/current.json`, a 256-byte pointer that names the immutable snapshot manifest, which in turn lists four artifact URLs (`snapshot`, `listIndex`, `facets`, `mapViews`). `snapshot.json` is the whole dataset. |
| Fetches used | 4 (page, pointer, manifest, snapshot). Gzip-encoded; needs `--compressed`. |
| Size / count | 37 MB, **35,505 places** (manifest `placeCount`: 35,504) |
| Last updated | `generatedAt: 2026-08-07T01:39:30Z` — **9 days old** |

**Fields exposed.** `id` (UUID), `lat`, `lng`, `name`, `city`, `state`,
`citySlug`, `streetAddress`, `location`, `sources[]`, `giftCard`,
`businessType`, `rank`, plus a nested `extra` object.

Coverage of `extra` across the whole set: `orderingUrl`, `profileUrl`,
`orderingStatus`, `sourceRestaurantUrls`, `websiteUrl` are near-universal;
`googlePlaceId` 827/35505, `rating` 572/35505, `neighborhood` 431/35505,
`phoneNumber` 720/35505. **There is no review-count field anywhere in the
dataset** — see "Enrichment gap" below.

`businessType` confirms the site's non-restaurant claim: 33,629 restaurants +
1,876 others (retail_services 996, beauty_wellness 425, fitness_nutrition 235,
arts_entertainment 90, specialty_lounges 52, auto_services 45, body_art 19,
pet_services 14).

`sources[]` labels provenance per record; 34,794 of 35,505 are `["clover-paze"]`
alone, the rest additionally carry `bilt` / `rakuten` / `resy` / `doordash` /
`inkind` / `rewards-network` tags. This is the strongest single piece of
evidence that the underlying merchant set is a Clover-Paze harvest.

A second endpoint, `…/restaurant-visibility/current.json` (revision 41,
2026-08-13), carries manual suppression rules keyed by
`sourceRestaurantId` — and those IDs are in **Clover merchant-ID format**
(e.g. `5QWCCDMZ1FNM1`), the same format awardhelper exposes as `merchantId`.

---

## 2. awardhelper.com — USED (secondary)

| | |
|---|---|
| Page | `https://www.awardhelper.com/paze-restaurants` |
| robots.txt | `Allow: /` for `*`, and **explicitly `Allow: /` for `ClaudeBot`**, GPTBot, PerplexityBot, Google-Extended, Applebot-Extended. |
| Data endpoint | `https://www.awardhelper.com/api/paze-restaurants` |
| How found | Not in the page HTML. Recovered from the Next.js chunk `328qph8fexnej.js`, which calls `fetch("/api/paze-restaurants")`. |
| Fetches used | 11 (page, 9 JS chunks, API) |
| Size / count | 8.5 MB, **28,704 records** (`total: 28704`) |
| Last updated | No dataset-level timestamp. Per-record `lastSeenActive` is present on 17,477/28,704 and the SF rows all read `2026-06-22T20:44:54Z` — **~8 weeks old** |

**Fields exposed.** `merchantId` (Clover merchant ID), `name`, `address`,
`city`, `state`, `lat`, `lng`, `orderUrl`, `pazeConfidence` (all `high` in the
SF slice), `lastSeenActive` (61%), `possibleInactive` (9,150), `merchantType`
(1,655; value `demo` marks test merchants), `possibleGiftCard` (1,599).

Strictly poorer than nextcard: no category, no rating, no neighborhood, no
ordering status.

### Note on the bot check

The client bundle wraps this endpoint in a protection shim that injects an
`x-is-human` header and lists `/api/paze-restaurants` under `protect` with
`checkLevel: "deepAnalysis"`. **I did not forge that header.** A plain,
self-identifying `GET` with no special headers returned HTTP 200 and the full
payload, so no access control was circumvented. If that ever starts returning
403, this source should be reclassified as manual-review rather than worked
around.

The bundle also carries a client-side blocklist of five merchant IDs
(`YY0M35JHFJYQ1`, `NA6SRHPVAN6N1`, `CCVFP2FRM9MD1`, `C1625EDB4BNJ1`,
`BPXVBNQPQH2H1`) and drops `merchantType == "demo"`. Both rules are applied as
*flags* rather than deletions in our extract, per the recall-first instruction.
None of the five appear in the SF slice.

---

## 3. pazemap.com — DECLINED, not scraped

`https://pazemap.com/robots.txt` carries a Cloudflare-managed block that
explicitly names this agent:

```
User-agent: ClaudeBot
Disallow: /
```

alongside `Disallow: /` for Amazonbot, Bytespider, CCBot, GPTBot,
Google-Extended, meta-externalagent, Applebot-Extended, and
CloudflareBrowserRenderingCrawler. The `User-agent: *` group sets
`Content-Signal: search=yes, ai-train=no, use=reference`.

Per the brief's ground rules this is a hard stop, so **no page, bundle, or API
on this domain was requested** — the robots.txt fetch is the only request made
to it. It is a manual-review source.

**This is the one real gap in the cohesion analysis**: it is a two-source
comparison, not the three-source one the brief asked for. See
`notes/cohesion.md` for why I think that gap is small in practice, and what
you can do by hand to close it.

## 4. pazemaps.com (plural) — DOES NOT RESOLVE

`NXDOMAIN`. The brief flagged it as unverified; it appears not to exist as a
public host at all. No further action.

## 5. mealmaxxer.com — DOES NOT RESOLVE

`NXDOMAIN` at that spelling. Not pursued; it was cross-reference material
(Bilt/Resy/inKind) rather than a Clover source, and nextcard already carries
those affiliations in its `sources[]` field.

---

## 6. Clover's own upstream — INVESTIGATED, unavailable

Step 5's preferred backfill was Clover's own public directory. **There isn't
one.**

- `https://www.clover.com/robots.txt` sets `Disallow: /v1/`, `/v2/`, `/v3/`
  for all agents — the REST API is off-limits to crawlers.
- The Clover REST API is merchant-scoped and OAuth-gated anyway
  (`/v3/merchants/{mId}/…`); it has no "list all merchants" route.
- Certificate Transparency was tried as an enumeration route
  (`crt.sh` was returning HTTP 502 on every attempt; Cert Spotter answered).
  Clover serves a **wildcard cert** — the only names on file are
  `*.cloveronline.com`, `*.dev…`, `*.staging…`, `*.apstaging…`, `*.jpdev…`.
  CT therefore reveals nothing about individual merchants. Dead end.

### What *is* usable: merchant subdomain robots + no wildcard DNS

Individual storefronts (e.g.
`https://16th-street-diner-san-francisco.cloveronline.com/robots.txt`) serve:

```
User-Agent: *
Allow: /
Disallow: /expired/
Disallow: /checkout/
Disallow: /confirmation/
Disallow: /customer-profile/
```

So fetching a storefront root is explicitly permitted, and `/checkout/` is
explicitly forbidden — which matches the brief's own rule about not probing
checkout. Nothing under those disallowed paths was requested.

Separately, `cloveronline.com` has **no wildcard DNS**: three nonsense
subdomains all returned `NXDOMAIN`, while real ones CNAME to
`preview.cloveronline.com`. That makes a DNS lookup a zero-HTTP-cost existence
test for an ordering page, which is what the step-5 backfill is built on.

## 7. OpenStreetMap / Overpass — USED (backfill place source)

The brief's step 5 fallback calls for "a places API". Google Places needs a
billing account, so I used Overpass, which is free and keyless.

- One POST to `https://overpass-api.de/api/interpreter` (the
  `overpass.kumi.systems` and `overpass.private.coffee` mirrors both returned
  504; the main instance 504'd once then succeeded).
- Query: food/drink/retail/beauty POIs inside the brief's bounding box.
- Result: 5,276 elements, **5,204 with a name** (4,710 distinct). 2.2 MB, cached.

### Backfill result: 3 new merchants

Method: OSM name → candidate Clover slug → DNS lookup → storefront
confirmation. **11,412 slugs probed, 5 DNS hits, 3 confirmed in SF.**

| Slug | Storefront name | Storefront city | Verdict |
|---|---|---|---|
| `dancing-yak-san-francisco` | DANCING YAK | SAN FRANCISCO | **new SF merchant** |
| `krispy-krunchy-chicken-san-francisco` | KRISPY KRUNCHY CHICKEN | SAN FRANCISCO | **new SF merchant** |
| `taqueria-san-jose-san-francisco` | TAQUERIA SAN JOSE | SAN FRANCISCO | **new SF merchant** |
| `the-outsider` | The Outsider | MANISTEE | rejected — Michigan |
| `krispy-krunchy-chicken` | KRISPY KRUNCHY CHICKEN | PLANO | rejected — Texas |

All three confirmed merchants report `paze.supported: true`. They appear in
`data/sf-candidates.csv` with `sources=inferred`.

Worth noting: `krispy-krunchy-chicken-san-francisco` is very likely the live
replacement page for `tl-kitchen-krispy-krunchy-chicken-san-francisco`, an
awardhelper record that is now NXDOMAIN. Both maps missed the new page.

The two rejects were both *bare* slugs (no `-san-francisco` suffix), which is
exactly the collision the storefront city check exists to catch. Their
addresses and coordinates in `data/raw/inferred-sf.csv` come from the matched
OSM POI rather than from the merchant, so they carry
`address-from-osm-name-match` in `notes` — treat the street address as a
hint, not a fact.

**Honest read on this method's yield: low.** Slug prediction only reproduces
64.8% of *known* slugs even when starting from the merchant's exact registered
name (`python3 scripts/slugrules.py` reports this), because a large minority of
Clover slugs simply do not derive from the display name — `Copper Chimney` is
`curry-kabab`, `Rockridge` is `united-dumplings`, `Catch Seafood` is
`catch-french-bistro`. Starting from OSM names, which differ again from the
registered names, compounds that. **Three finds is a floor, not a ceiling** —
there are probably more SF Clover merchants that neither map lists and this
method cannot reach. See `notes/cohesion.md` for what that means for coverage
confidence.

## 8. Clover storefront page roots — USED (Paze verification)

**This one changes an assumption in the brief.** You expected checkout
verification to be manual. It doesn't have to be.

A Clover storefront's page root embeds its own payment configuration:

```json
"paze": {"supported": true, "client_id": "K007HM1XL0DWJX3OR6..."}
"launchDarklyFeatures": [{"name": "PAZE_ON_COLO2", "enabled": true}, ...]
```

and its city in the meta description (`"…Based in SAN FRANCISCO."`). So
whether Paze is wired up is readable from the same page a browser loads before
you put anything in a cart.

**Nothing in the brief's prohibition was touched.** The rule was "do not
automate anything past a merchant's add-to-cart step" — no cart was created, no
checkout was opened, no payment flow was exercised. Only `GET /` was requested,
which every merchant's robots.txt explicitly allows while disallowing
`/checkout/`, `/confirmation/`, and `/customer-profile/`. 1 request/second,
self-identified.

**Result: 203 of 203 live storefronts report `paze.supported: true` with
`PAZE_ON_COLO2` enabled.** Recorded as `paze-on-storefront=yes` in the `notes`
column. Zero negatives, one transient 502 that succeeded on retry.

Two caveats on what this proves:

- It is a **confirmation, not a filter**. Since every candidate passes, it does
  not narrow your shortlist. What it buys you is that the community maps are
  not padded with false positives, so your manual pass is about hours, menu and
  appeal rather than hunting for a Paze button.
- It reports that the storefront's payment config *offers* Paze. It cannot tell
  you the button renders for your specific card, or that the merchant is
  currently accepting orders. `verified` is therefore still blank, as you asked
  — this is evidence for your manual pass, not a substitute for it.

The same fetch independently caught nine merchants whose storefronts
self-report a non-SF city (`RIVERSIDE`, `PORTLAND`, `SACRAMENTO`, `REDDING`,
`VALLEJO`, `DALY CITY`) — corroborating the address-based `city-mismatch`
flags from a second, independent direction.

## 9. DataSF — USED (neighborhood boundaries)

- `https://data.sfgov.org/resource/gfpk-269f.geojson` ("SF Find
  Neighborhoods"), 117 polygons, 294 KB.
- robots.txt sets `Crawl-delay: 1` and disallows only faceted `/browse`
  query-strings; `/resource/` is unrestricted.
- Note: the `xfcw-9evu` ("Analysis Neighborhoods") ID returned
  `dataset.missing`; `gfpk-269f` is the one that works.
- Used for point-in-polygon neighborhood tagging *and* as the real SF-proper
  test, which is stricter than the bounding box alone.

---

## Enrichment gap — `review_count` could not be filled

The output schema asks for `google_rating` and `review_count`, and step 7 says
to do it "if you can do it within API free tiers". I could not:

- **Neither source carries a review count.** nextcard has `rating` on
  572/35,505 records overall and only **7 of the 139** SF rows; there is no
  count field at all. awardhelper has neither.
- **Google Places API has no free tier that covers this.** It requires an API
  key attached to a billing account. There is no key in this environment, and
  creating one is your call, not mine.
- Scraping Google search results for ratings would breach Google's robots.txt,
  so it was not attempted.

`google_rating` is therefore populated for 7 rows and `review_count` for none.
Because the brief asked to sort by `review_count` descending and that column is
empty, **the CSV is sorted by name instead** — a sort on an empty column would
have implied a ranking that does not exist.

To close this: a Google Maps Platform key (Places API "Text Search", ~$32/1000
requests, with a recurring monthly credit that comfortably covers ~150 lookups)
would let me fill both columns in one rate-limited pass. Say the word and hand
me a key, and I will run it.
