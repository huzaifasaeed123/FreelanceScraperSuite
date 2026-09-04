# 75 — Maps Scraper

Google Maps business-listing scraper: parallel, resumable, and fixed for two
real bugs that silently corrupt data if you don't know to check for them
(non-Latin keyword filenames, and headless Chrome's stripped-down page).

## Two folders, two purposes

**[client-delivery/](client-delivery/)** — the actual client engagement.
Real target lists, real output data, real dated deliveries, kept exactly as
delivered for full traceability. Two phases: a completed 16-country run
(121,158 businesses) and an in-progress 6-country gap-fill batch. Not meant
to be edited or reused as a starting point for new work.

**[general-scraper/](general-scraper/)** — the same engine and fixes,
generalized and documented for reuse on any future Maps scraping job.
Configurable worker count, pluggable target lists (`countries/_TEMPLATE.py`),
full deployment runbook. Start here for a new job.

Read `general-scraper/README.md` first if you're about to run this for
something new — it explains the control panel (`--workers`, `--countries`,
etc.), the two fixes you must not lose, and what "resume-safe" actually
guarantees. Read `client-delivery/README.md` for the story of how this
project got to its current state.

## Not part of either folder

- `ahmed.py` — a stray one-line test file, unrelated to this project.
- `UHS SLip 2026/` — a different scraper (MDCAT admit-card PDFs) that ended
  up nested in this folder by accident; its intended location no longer
  exists on disk. Left untouched rather than guessed at — move it or delete
  it as appropriate.

Both are excluded from git via `.gitignore` below.

## Data and inputs are not in git

Every output dataset and every job-specific target list (the real
`countries/*.py` files under `client-delivery/`) lives on disk here but is
excluded from version control — see `.gitignore`. Git tracks the scraper
code, the fixes, and the documentation; it does not track scraped business
data or client-specific input lists. The `general-scraper/countries/`
template *is* tracked, since it's documentation/starter code, not real data.
