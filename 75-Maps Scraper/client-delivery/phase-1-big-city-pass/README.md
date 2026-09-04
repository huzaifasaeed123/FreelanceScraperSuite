# Phase 1 — Big City Coverage Pass

**Status: complete.** 16 countries, 3,262 city x keyword searches, 100%
coverage (`fail=0 skip=0`), **121,158 unique businesses**. Scrape finished
2026-08-23 03:50 CEST; final delivery verified and sent 2026-08-24.

## What was asked

The client supplied a working single-threaded scraper (`README_AS_RECEIVED.md`,
`run_countries72.py`) and a sample output file (`client-reference/`) covering
16 countries, and reported two problems: opening hours only showing 1 day
instead of 7, and `reviews_count` always coming back `null`. They asked for
it run to completion across all 16 countries.

## What was actually wrong, and what was done

Documented in full in `DEPLOYMENT.md`. Short version: both complaints were
real, and one root cause explained both — headless Chrome's default
User-Agent gets served a stripped-down page by Google. Fixed with a UA
override, plus the opening-hours table parser and the `reviews_count`
selector both needed rebuilding for Google's current DOM (verified
side-by-side: 1 day -> 7 days, `null` -> 1,572 real reviews count, same URL,
same minute).

The original code was also sequential — one browser, ~15-16 days estimated
for the full pass. Parallelized to up to 6 workers (`run_parallel.py`,
written for this engagement) plus several page-load optimizations, without
changing what data was collected (same 10 fields, same single page-visit
per business).

A second, more serious bug was found partway through: `safe_filename()`
stripped non-Latin characters, so Japanese/Arabic keywords collapsed onto a
single shared filename per city, and the resume logic then treated the
first keyword's file as proof the whole city was done — silently skipping
the rest. This is why **Japan's final count (14,943) is ~12x its first
partial pull (1,201)** — caught and fixed mid-run, average cost model and
full story in `../phase-2-week4-missing-coverage/README.md` where it
resurfaced and was properly root-caused.

A separate infrastructure issue also cost real time: 6 parallel workers on
the 11 GB server exceeded a 9 GB memory cap and got OOM-killed roughly every
13 minutes — since one combo takes 20-50 minutes, this meant the service
"ran" for hours making zero net progress. Fixed by dropping to 4 workers
with a proper `MemoryHigh`/swap safety net (see `general-scraper/DEPLOYMENT.md`
for the generalized version of this fix).

## Final numbers by country

| Country | Businesses |
|---|---:|
| India | 15,921 |
| Japan | 14,943 |
| Brazil | 12,837 |
| Canada | 10,089 |
| United States | 9,278 |
| Spain | 8,976 |
| Saudi Arabia | 6,842 |
| Italy | 6,104 |
| Germany | 6,078 |
| Australia | 6,009 |
| Russia | 5,956 |
| United Kingdom | 5,488 |
| France | 5,384 |
| Mexico | 4,997 |
| Sweden | 1,387 |
| Norway | 869 |
| **Total** | **121,158** |

Field coverage across all 121,158 records: name/coordinates/Maps URL 100%,
rating 97.7%, reviews_count 96.2%, phone 91.9%, image 87.9%, opening hours
with all 7 days 77.6% (10.9% partial, 11.5% missing — genuinely absent from
the business's Google listing, not a scraping gap). Full detail in
`output/FINAL_2026-08-23/_MANIFEST.txt`.

## Folder contents

```
README_AS_RECEIVED.md    the client's own instructions, as originally supplied
client-reference/         the client's sample output file (the target format/schema)
DEPLOYMENT.md              the fixes: what was broken, why, and how each was fixed
HOW_TO_USE.md              day-to-day server operating reference (ssh/scp/systemctl commands)
code/                      the engine + runner AS RUN for this phase (fixes applied)
output/                     every delivery snapshot taken during the engagement, in order:
  2026-08-11/                first progress pull (partial)
  2026-08-18/                 second progress pull, still partial
  CLIENT_DELIVERY_1_2026-08-18/   first real client delivery - 11 countries at genuine 100%
  FINAL_2026-08-23/               final complete delivery - all 16 countries, 121,158 businesses
  MapsData_Final_16Countries_121158.zip   the exact zip file sent to the client
```

`code/countries/` holds the real 16 target lists used for this run (cities +
keywords per country) — job-specific input, not reusable code. For a fresh
target list format to start a new job, see
`../../general-scraper/countries/_TEMPLATE.py`.
