# Phase 2 — Week 4 Missing Coverage

**Status: IN PROGRESS as of the last data pull (2026-09-02, 14:48 UTC).**
The `output/` in this folder is that pull, not a final delivery — do not
send it to the client as complete. The live server was unreachable when
last checked (2026-09-04); reconnect and check `code/as-run/status.sh` for
current status before pulling fresh data or declaring this finished.

## What this phase is

A gap-fill batch: the client's own tooling
(`build_missing_coverage_scrapers.py`, not included here) flagged specific
(city, keyword) combinations below 75% coverage from earlier work and
generated target lists for 6 countries — Ghana, Uruguay, Bahrain, South
Africa, India, and Japan — **4,790 combos total**, deliberately scoped to
neighbourhoods/keywords *not* already covered by the Phase 1 Big City Pass
run (see `code/as-received-from-client/remove_duplicates.py`, the client's
own de-duplication tool between the two phases).

## Last known progress

| Country | Combos | Status | Businesses |
|---|---:|---|---:|
| Ghana | 30 / 30 | complete | 1,446 |
| Uruguay | 30 / 30 | complete | 1,733 |
| Bahrain | 371 / 371 | complete | 3,125 |
| South Africa | 414 / 414 | complete | 13,458 |
| India | 981 / 2,160 | in progress | 44,986 |
| Japan | 0 / 1,785 | not started | 0 |
| **Total** | **1,826 / 4,790 (38.1%)** | | **64,748** |

Four of six countries are genuinely complete and safe to treat as final
(verified by file count against each country's real `cities x keywords`
total, not just the counter above — see the filename-bug note below for why
that distinction matters). India and Japan are not.

## Why this phase exists as a separate deployment from Phase 1

The client's original code for this batch (`code/as-received-from-client/`)
is the same single-threaded engine as Phase 1's original — unpatched,
un-parallelized. Rather than rerun Phase 1's fixes from memory, the proven
fixed+parallelized deployment was redeployed fresh for this batch
(`code/as-run/`), on the same server, sharing the same lessons.

## The bug this phase caught properly

This batch is where the non-Latin filename bug (see
`../phase-1-big-city-pass/README.md` and `general-scraper/README.md`, fix
#4) was actually root-caused and fixed — it had already quietly cost ~95% of
Phase 1's Japan data before anyone noticed the pattern. This batch's Japan
target list is **100% non-Latin keywords** (all 21 keywords are Japanese),
making it the clearest possible case: pre-fix, only 11 of 352 combos would
resolve to distinct files; the fix makes all 352 resolve correctly. Full
mechanism and the fix itself: `code/as-run/googlescrap72.py`'s
`safe_filename()`, and `../DEPLOYMENT.md` / `general-scraper/DEPLOYMENT.md`
for the pre-flight check that should run before scraping any new non-Latin
target.

## Folder contents

```
DEPLOYMENT.md                          the memory-livelock fix + redeployment story for this batch
code/
  as-received-from-client/              the client's original single-threaded code, unpatched -
                                          kept as historical record, do not run this as-is
    README_AS_RECEIVED.md                 the client's own instructions for this folder
    countries/                             the 6 real target lists as originally supplied (+ .bak files)
  as-run/                                what actually ran on the server - fixed engine,
                                          parallel runner, systemd service, requirements.txt
    countries/                             the same 6 target lists (identical content to as-received)
output/                                  latest data pull (2026-09-02) - PARTIAL, see status above
```

## Before treating this as finished

1. Reconnect to the server and check `code/as-run/status.sh` for real
   current progress.
2. Pull fresh data the same way Phase 1's deliveries were built (compress
   server-side first — `output/_merged/` is tens of MB, the link is slow).
3. Re-verify India and Japan by real file count
   (`ls output/<country> | wc -l`) against their true combo counts (India:
   90 cities x 24 keywords = 2,160; Japan: 85 cities x 21 keywords = 1,785)
   before declaring either complete — the summary counter can over-report
   if it's counting pre-fix collapsed files.
