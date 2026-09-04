# Deployment — Google Maps Big City Pass

Server: `root@169.58.117.156` (Ubuntu 24.04, 6 cores, 11 GB RAM)
Install root: `/opt/maps-scraper`

## What was fixed (and why the client's two complaints were both real)

The client said the code works; you saw it not working. Both were true, and
the cause was one thing.

**Headless Chrome advertises `HeadlessChrome/...` in its User-Agent, and
Google serves that UA a stripped-down page** — one day of opening hours
instead of seven, and no review count at all. The client ran it somewhere
that didn't hit this; you ran it headless, as the README instructs.

Verified on 2026-08-05, same URL, same machine, same minute:

| | opening hours | reviews_count |
|---|---|---|
| headless, default UA | 1 day | `null` |
| headless, spoofed UA | **7 days** | **1572** |

Fixes applied to `googlescrap72.py`:

1. **User-Agent override** (`--user-agent=...Chrome/151.0.0.0...`) — the root
   cause fix. Restores the full payload while staying headless.
2. **Hours expander selector** — the old selector targeted an icon `<span>`
   that has the `aria-label` but no click handler. The real control is its
   `role="button"` ancestor carrying a `pane.openhours` jsaction.
3. **Hours table parsing** — Google now renders all 7 days inside a single
   `<tr>`; the old code read `cells[0]`/`cells[1]` and so returned one day
   even when the data was present. Now walks every cell, pairing day/time.
   A per-day `aria-label` parser backs it up if the markup shifts again.
4. **reviews_count** — the three legacy selectors match nothing on the
   current DOM. Now reads the `(1,572)` figure from the rating block.
5. **image** — accepts any photo ≥150px wide instead of only `w256`/`w408`
   (Google now also serves `w224`), while excluding avatars.
6. **Dead import removed** — `webdriver_manager` was imported but unused, and
   crashed on any machine without that package installed.

## Speed work

Original: sequential, one browser, ~15–16 days for the full pass.

- **6 parallel workers** (`run_parallel.py`), one per core.
- **`pageLoadStrategy=eager`** — `driver.get()` used to block until Maps
  finished fetching tiles and telemetry long after the data was in the DOM.
  Roughly halved page-load time.
- **Tile/telemetry blocking** via CDP — none of the ten fields come from map
  tiles, and blocking them cuts the bandwidth six browsers share.
- **Images disabled** — the image *URL* still comes through the DOM, so the
  `image` field survives; we just don't download the bitmaps.
- **Condition-based waits** replacing blind `time.sleep()` — the code slept a
  fixed 4s per business for a page that was usually ready far sooner.
- **Cross-variation dedup** — `"X in Y"` and `"X near Y"` return heavily
  overlapping results; already-scraped places are now skipped rather than
  re-opened and re-parsed.

No extra page visits were added. Everything (including opening hours and
review count) still comes from the single business detail page, as before.

## Operating it

```bash
systemctl start maps-scraper      # begin / resume the run
systemctl stop maps-scraper       # pause (safe at any moment)
systemctl status maps-scraper
/opt/maps-scraper/status.sh       # progress, counts, health
tail -f /opt/maps-scraper/logs/runner.log
```

**Resume-safety**: every `(city, keyword)` combo writes its own checkpoint
file the moment it completes (an empty `[]` file if it genuinely found
nothing). Restarting re-scans and skips finished work. Killing the box
mid-combo loses at most that one combo. Files are written to a temp name and
atomically renamed, so a snapshot taken mid-write never sees a partial file.

## Getting the data out

Merged exports are rebuilt every 5 minutes while running:

```
/opt/maps-scraper/output/_merged/ALL_COUNTRIES.json   # everything, deduped
/opt/maps-scraper/output/_merged/<country>.json       # per country
/opt/maps-scraper/output/_merged/SUMMARY.json         # counts + timestamp
```

A zipped snapshot is written hourly by cron to
`/opt/maps-scraper/snapshots/`, with `latest.zip` always pointing at the
newest. To download from your PC:

```bash
scp root@169.58.117.156:/opt/maps-scraper/snapshots/latest.zip .
```

So if you come back after a day, `latest.zip` already has everything scraped
up to the last hour, and `status.sh` tells you how far along it is.

## Output format

Unchanged from the client's sample — same keys, same order, same types. The
only difference is that `open_hours` now has all 7 days and `reviews_count`
is populated instead of `null`.
