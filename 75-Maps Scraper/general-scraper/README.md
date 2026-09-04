# Maps Scraper — general-purpose engine

Reusable Google Maps business scraper. Give it a list of (city, keyword) pairs,
it collects name / phone / website / coordinates / opening hours / rating /
review count / photo / Maps URL for every match, running several browsers in
parallel with resumable, checkpointed progress.

This is the fixed, hardened version of the engine — see "Fixes baked into
this copy" below before assuming a bug you hit is new. It was proven across
two real client engagements (see `../client-delivery/`) totaling ~155,000
businesses across 22 countries, with zero data loss from crashes, restarts,
or reboots.

## Quick start

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Get Chrome + chromedriver (must be a matched pair — see DEPLOYMENT.md).

Define what to scrape: copy `countries/_TEMPLATE.py` to `countries/<name>.py`
and fill in your city list and keywords (full interface documented in the
template).

Run:

```bash
venv/bin/python run_parallel.py --workers 4
```

That's it — with no `--countries` flag, it auto-detects and runs every
`*.py` file in `countries/`. Progress streams to `logs/runner.log`, results
land in `output/<name>/`, and a live-updated merged export appears in
`output/_merged/` every `--export-every` seconds (300 by default).

## The control panel — every option

```
--workers N          parallel browser instances (default 6 - see "Sizing
                      workers to RAM" below, this is a memory limit, not a
                      CPU one)
--countries a b c     which countries/targets to run, and in what order
                      (default: every file in countries/, alphabetical).
                      Order matters - listed countries are worked through
                      front-to-back, so put anything time-sensitive first.
--max-per-search N    cap results per individual search (default 120)
--jitter N            max random delay before each combo, seconds (default
                      3.0 - avoids all workers hitting Maps in lockstep)
--export-every N      seconds between merged-export rebuilds, 0 disables
                      (default 300)
--export-only         skip scraping, just rebuild output/_merged/ from
                      whatever's already on disk, then exit
--limit N             process at most N combos - use this for a smoke test
                      before committing to a full run
```

Run a tiny sanity check before trusting a new country file or a new server:

```bash
venv/bin/python run_parallel.py --countries yournewcountry --limit 3
```

## Sizing workers to RAM

**This is memory-bound, not CPU-bound.** Each headless Chrome instance runs
1.5-2 GB through a combo. The proven ceiling on an 11 GB box is **4 workers**
with a `MemoryHigh`/swap safety net (see DEPLOYMENT.md) - 6 workers on that
same box caused an OOM-kill every ~13 minutes, and since one combo takes
20-50 minutes, **nothing ever finished**: the service looked "running" while
making zero net progress for hours. More cores does not mean more workers is
safe; more free RAM does.

Rule of thumb: budget ~2 GB/worker, leave several GB of headroom, and
soak-test any new number for 30-60 minutes (watch for OOM-kills) before
trusting it for an unattended multi-day run.

## Fixes baked into this copy — do not lose these

1. **Headless User-Agent spoofing.** Headless Chrome's default UA gets a
   stripped-down page from Google (1 day of opening hours instead of 7, no
   review count). Fixed with an explicit `--user-agent=...` override that
   keeps `--headless=new` working while getting the full page.
2. **Opening-hours parsing** rebuilt for Google's current markup (a single
   `<tr>` holding all 7 days, not one row per day), with a per-day
   `aria-label` fallback if the DOM shifts again.
3. **`reviews_count`** now reads the real figure from the rating block - the
   original selectors matched nothing on the current DOM and always
   returned `null`.
4. **Non-Latin keyword filenames** (the most consequential fix). Filenames
   were built by stripping every non-Latin character - a keyword in
   Japanese/Arabic/Hindi/Cyrillic has nothing left after stripping, so every
   such keyword in a city collapsed onto the same filename, and the resume
   logic then treated the first keyword's file as proof the *whole city* was
   done, silently skipping the rest. This cost ~95% of one country's data on
   a real run before it was caught. Fixed by falling back to a content hash
   when the stripped slug is empty - see `safe_filename()`. **Before running
   any new country file with non-Latin keywords, verify no two keywords for
   the same city produce a colliding filename** (a five-line check - see
   DEPLOYMENT.md's pre-flight section).
5. **Resume-safety on zero-result combos.** A combo that genuinely finds
   nothing now still writes an empty `[]` checkpoint file, so it's marked
   done rather than retried forever on every restart.

## What "resume-safe" actually guarantees

Every `(target, city, keyword)` combo writes its own output file the instant
it finishes - success or genuine zero results alike. `Ctrl+C`, a crash, a
service restart, or a full box reboot loses at most the handful of combos
that were mid-flight when it happened; everything else is skipped on restart,
not re-scraped. This is what makes it safe to run unattended for weeks and
to move mid-run to a different, better-specced server.

## Getting data out

```
output/<target>/<target>_<city>_<keyword>_comprehensive.json   per-combo checkpoints
output/_merged/<target>.json                                    merged, deduped, per target
output/_merged/ALL_COUNTRIES.json                                everything, concatenated
output/_merged/SUMMARY.json                                      counts + completion status per target
```

`status.sh` (copy it to wherever the scraper runs, `chmod +x`) prints a live
progress report: combos done/total, per-target completion, and where the
latest export lives. Its per-target percentage is a *counter*, not a disk
check - cross-verify with `ls output/<target> | wc -l` against that target's
real `cities x keywords` count if a number looks off (this is exactly how
the filename bug above was originally caught).

`snapshot.sh` zips the current `output/` on demand — wire it to cron for
automatic hourly snapshots if running unattended.

## Deploying to a server

See `DEPLOYMENT.md` for the full runbook: Chrome/chromedriver setup,
`requirements.txt`, systemd unit, memory tuning, and a pre-flight checklist
for any new target before committing to a long unattended run.
