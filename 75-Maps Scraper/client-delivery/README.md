# Client project — Google Maps business data

A Google Maps business-listing scrape delivered in two phases for the same
client. Everything in this folder — code as delivered/as-run, every output
snapshot, and the client's own original files — is kept for full traceability
of what was asked, what was delivered, and what was fixed along the way.

## The two phases

**[phase-1-big-city-pass/](phase-1-big-city-pass/)** — the original
engagement. 16 countries, 3,262 searches, **121,158 businesses**, complete.
The client supplied a working-but-broken single-threaded scraper; this phase
fixed two real bugs (opening hours, review counts — both caused by the same
root issue), rebuilt it to run 6 browsers in parallel, and delivered the
full dataset.

**[phase-2-week4-missing-coverage/](phase-2-week4-missing-coverage/)** — a
follow-up gap-fill batch, using the client's own tooling to target
neighbourhoods/keywords not covered in phase 1. 6 countries, 4,790 searches.
**In progress** — see that folder's README for current status before
treating any of its data as final.

## The throughline between the two phases

Both phases used the same underlying engine, and the most consequential bug
— non-Latin keywords (Japanese/Arabic/Hindi/Cyrillic) silently collapsing
onto shared filenames and losing ~95% of affected data — first appeared in
Phase 1 (Japan's numbers jumped ~12x once caught) and was properly
root-caused and fixed during Phase 2, where the Japan target list is 100%
non-Latin keywords and makes the bug impossible to miss. The fix and the
reasoning behind it now live in `general-scraper/` (`../general-scraper/`)
as a permanent, reusable part of the engine, so it can't be silently lost or
reintroduced in a future job.

## What's real client work vs. reusable tooling

This folder is the historical record — real target lists, real output data,
real dated deliveries, kept exactly as they were sent or as they currently
stand. The `code/` inside each phase is a snapshot of what actually ran, not
meant to be edited going forward.

For starting a *new* scraping job (different client, different cities,
different categories), use `../general-scraper/` instead — the same fixed
engine, generalized and documented for reuse, with none of this phase's
specific target data baked in.
