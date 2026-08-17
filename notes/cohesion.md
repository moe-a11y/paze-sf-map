# Cohesion: are the community maps one dataset or three?

> **Scope note (updated).** This project originally covered San Francisco
> proper. It now covers **SF plus the northern Peninsula** — Daly City, Colma,
> Brisbane, South SF, San Bruno, Millbrae, Burlingame, Hillsborough, San Mateo,
> Foster City, Pacifica, Belmont, San Carlos. Totals below are the expanded
> area: **212 merchants**, up from 147 SF-only.
>
> Selection now runs **three parallel recall channels** — coordinates, city +
> state text, and the Clover slug — because coordinate-only filtering silently
> drops records that are geocoded wrong. That is not hypothetical: *Taqueria Mi
> Durango II*, 671 El Camino Real in South San Francisco, carries coordinates
> in San Jose and was invisible to the original filter.
>
> A trap worth recording: matching on city name alone pulls in **Hillsborough
> NC**, **Hillsborough NJ** and **Burlingame KS**, plus "Pacifica" occurring
> inside a business name in Grover Beach CA. A `state = CA` constraint is
> required, not optional.

**Short answer: they are one upstream dataset, sampled at different dates.**
The 21% disagreement between them is almost entirely *staleness*, not
independent coverage. nextcard is the fresher, richer copy and you can treat it
as authoritative for this area.

One caveat up front: this is a **two-source** comparison, not the three-source
one the brief asked for. `pazemap.com` disallows this agent in robots.txt, so
it was not fetched at all (see `notes/sources.md` §3). What follows argues why
that gap is probably small — but it is an argument, not a measurement.

---

## The overlap table

Entities resolved across the expanded area, matched on normalized
`cloveronline` subdomain first and a name + street-address key second:

| Bucket | Merchants | Share of union |
|---|---:|---:|
| In **both** sources | 166 | 79.4% |
| **nextcard** only | 35 | 16.7% |
| **awardhelper** only | 8 | 3.8% |
| Backfill only (`inferred`) | 4 | — |
| **Total rows** | **212** | |

Per-source recall against the two-map union: **nextcard 96.2%**,
awardhelper 83.3%. Raw row counts before entity resolution: nextcard 201,
awardhelper 175.

(SF-only figures, for reference: 110 both / 28 nextcard / 6 awardhelper = 144,
76.4% overlap.)

79.4% two-way overlap sits below the brief's 90% threshold, which by the letter
of step 3 means "independently assembled, union everything." **The liveness
check below shows that reading is wrong.**

## The liveness check that settles it

Every one of the 212 `clover_url`s was resolved and fetched at its root
(1 req/sec; `/checkout/` never touched — it is robots-disallowed on merchant
subdomains anyway). Results by bucket:

| Bucket | Rows | Dead URL (NXDOMAIN) | Dead % |
|---|---:|---:|---:|
| Both sources | 166 | 2 | 1.2% |
| nextcard only | 35 | **0** | **0.0%** |
| awardhelper only | 8 | **7** | **87.5%** |
| Backfill (`inferred`) | 4 | 0 | 0.0% |
| All | 212 | 9 | 4.2% |

Widening the area made the signal *stronger*, not weaker: awardhelper's
exclusives went from 83.3% dead to 87.5% dead, while nextcard's stayed at zero
across 35 records.

The SF-only seven were re-checked individually with `host` and all seven are true
`NXDOMAIN` — the ordering subdomain has been withdrawn, not a transient blip.
A live control (`alborz-san-francisco`) resolves normally.

That 87.5% vs 0% split is the whole story. If the two sites had assembled their
lists independently, each one's exclusives would look statistically alike.
Instead:

- **awardhelper's exclusives are dead merchants** — pages that existed when it
  harvested and have since been taken down. It is not finding merchants
  nextcard missed; it is *failing to notice* merchants nextcard has already
  dropped.
- **nextcard's 35 exclusives are 100% live** — these are real merchants
  awardhelper simply has not picked up yet.

The dates corroborate it exactly. nextcard's snapshot is stamped
`2026-08-07`. Every awardhelper record in this area carries
`lastSeenActive: 2026-06-22` (~8 weeks old). Six extra weeks of merchant churn
in a long-tail restaurant population is more than enough to produce a 24%
symmetric-difference.

### The one apparent exception isn't one

Exactly one awardhelper-exclusive merchant is live: `SOY GRILL TERIYAKI`,
slug `soy-grill-teriyaki-portland`, address *"9738 Sf Washington St #w,
**Portland, OR**"*. awardhelper geocoded it to `37.774929, -122.419415` — the
default San Francisco centroid — which is why it fell inside the bounding box
at all. It is a geocoding failure, not an SF merchant.

**So awardhelper contributes zero genuine live merchants that nextcard does not
already have.** Its practical marginal value for this project is nil.

## Evidence they share one upstream

Beyond the liveness asymmetry:

1. **Identical slug strings.** All 166 shared merchants match on the exact
   `cloveronline` subdomain, including irregular ones no two independent
   harvesters would coin the same way — `angel-cafe-deli-san-francisco8`,
   `tacos-el-patron-sf-san-francisco-2`, `crostiniandjavasf`,
   `b-b-cafe-san-francisco` (for a business displayed as "Bandb Cafe"). Those
   are pulled from Clover, not derived from the business name.
2. **Same key space.** awardhelper exposes `merchantId` in Clover's format
   (`SJGRV5201WVT1`); nextcard's suppression-rules file uses the same format in
   `sourceRestaurantId` (`5QWCCDMZ1FNM1`) and labels the provenance
   `"source": "clover-paze"`.
3. **nextcard labels it outright.** 34,794 of its 35,505 records carry
   `sources: ["clover-paze"]`.

Both sites are harvesting the same thing: the set of Clover merchants with a
Paze-enabled online-ordering page. Neither has privileged access; they differ
in when they last looked and how much they decorate the result.

## What this means for the build

Per step 3's decision rule, high cohesion means "pick the richest one and move
on." The measured 79.4% says otherwise, but the diagnosis says the divergence
is staleness — so the *spirit* of the rule applies: **nextcard is the richest
and freshest, and it alone covers 198 of the 203 live merchants (97.5%).** The
five it misses are the four backfill finds plus awardhelper's one live
exclusive, which is the mis-geocoded Portland record.

I still shipped the union, because the brief prioritizes recall and the cost of
carrying 9 dead rows is one glance each. They are flagged
`clover-url-dead(unreachable)` in the `notes` column so you can filter them in
one pass.

## What an independent third method found

Because measured cohesion was below 90%, step 5's backfill ran: OpenStreetMap
POI names → predicted Clover slugs → DNS resolution → storefront confirmation.
**18,496 slugs probed, 6 DNS hits, 4 confirmed merchants that neither map
lists** (3 in SF, 1 in Daly City).

That is a genuinely independent probe — it starts from a street-level POI
census rather than from anyone's Clover harvest — and it says two things at
once:

- **The maps are not complete.** Four real, live, Paze-enabled merchants were
  missing from both. One of them,
  `krispy-krunchy-chicken-san-francisco`, appears to be the replacement page
  for a merchant awardhelper still lists at a now-dead URL. Both maps missed
  the migration.
- **But they are not badly incomplete either.** A 5,771 name+city sweep of the
  whole area surfaced only four additions to a 212-merchant list.

The second point needs a caveat that cuts against it: this method's recall is
poor by construction. Slug prediction reproduces only 64.8% of *known* slugs
even when fed the merchant's exact registered name, because many Clover slugs
bear no relation to the display name at all. Feeding it OSM names compounds the
error. **Four is a floor on what's missing, not a ceiling.**

## The pazemap.com gap

`pazemap.com` is unmeasured. Two reasons to expect it adds little:

- It would have to be drawing on the same Clover-Paze merchant set — there is
  no other upstream. Its differentiators as described are *presentation*
  (bilingual EN/中文, rating and gift-card filters), not sourcing.
- nextcard's 35,504 is already the largest claimed figure of the three, and it
  is the only one claiming non-restaurant merchants — which it substantiates
  (1,876 non-restaurant records, 4 of them in SF).

But "expect" is doing real work in that sentence, and I would rather flag it
than paper over it. **If you want the gap closed, open `pazemap.com` in your
browser, filter to San Francisco, and export or copy the list.** Hand me
anything — CSV, a pasted table, a screenshot — and I will union it in and
re-run this comparison as a genuine three-way in a couple of minutes. Nothing
downstream has to change.
