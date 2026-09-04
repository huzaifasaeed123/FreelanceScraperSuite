# Big City Coverage Pass

Standalone scraper folder — copy this whole folder to any PC and run it
there. Fully self-contained (own `countries/`, `googlescrap72.py` engine,
`run_countries72.py` launcher); doesn't touch any other server_* folder
or PC.

## Countries in this batch
Canada, Germany, France, United Kingdom, United States of America, Saudi Arabia, Sweden, Norway, Spain, Italy, Russia, Mexico, Brazil, Japan, India, Australia

## Setup (do this before running, every time you move this folder to a new PC)

1. **Drop `chromedriver.exe` in this same folder**, next to
   `googlescrap72.py`. This is NOT included in this folder — you supply
   it per PC.
2. **Check it matches the Chrome version installed on that PC**
   (`chrome://version` in Chrome, compare the major version number
   against your chromedriver build). A mismatched chromedriver is the
   most likely cause of instant/silent failures.
3. That's it — no other setup. `googlescrap72.py` resolves
   `chromedriver.exe`'s path relative to its own folder
   (`Path(__file__).resolve().parent / "chromedriver.exe"`), not a
   hardcoded drive letter, so this works unmodified on any PC as long as
   the two files sit together.

## Running

```
python run_countries72.py
```

Runs headless (no visible browser window) — this is intentional, not a
bug. Watch the console for `Searching for ...` / `Saved N unique places
to ...` lines to confirm it's actually working.

## Resume-safety

Safe to stop (Ctrl+C) and restart at any time — nothing is lost.
`googlescrap72.py` checks each `(city, keyword)` combo's output file
before scraping it; already-done combos (found something, or genuinely
found nothing) are skipped automatically. On restart, `run_countries72.py`
always starts back at the first country in its list — this is expected,
it'll just fast-skip everything already done before reaching new work.

**To confirm resume-safety is actually working**: after a combo finishes
(look for a `_comprehensive.json` file inside this folder's
`<country>/` subfolder), stop and restart — you should see `SKIP (new
format exists)` for that exact combo instead of it re-scraping.

## Moving to another PC mid-run

Copy the **whole folder**, including the per-country output subfolders
(e.g. `canada\`) — that's where the resume-safety checkpoint files live.
The loose files directly in this folder's root (if any) are just
intermediate per-search-variation output, not required for resume, safe
to leave behind.

## Known fixes already baked into this copy (2026-07-15)

- **Resume-safety**: `googlescrap72.py` used to only write an output file
  `if unique_data:` — a legitimate zero-result combo never got marked
  done, so it was retried forever on every restart. Fixed to always
  write (an empty `[]` file marks it done).
- **ChromeDriver path**: used to call `ChromeDriverManager().install()`
  to auto-download a driver, which silently failed on the real scraping
  PCs and caused every search to throw instantly. Fixed to resolve
  `chromedriver.exe` relative to this folder instead — see Setup above,
  you must supply the binary yourself.
- **`python3` not found on Windows**: `run_countries72.py` used to call
  `python3` explicitly, which doesn't exist on Windows (only `python`),
  causing a "Python was not found... Microsoft Store" error per country.
  Fixed to use `sys.executable` (whatever Python is currently running
  the script) instead.
