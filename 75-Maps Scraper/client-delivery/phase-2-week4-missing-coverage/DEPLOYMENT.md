# Maps scraper — redeployment guide

This is the working, fixed, battle-tested version of the scraper as deployed and
run on 169.58.117.156 (`/opt/maps-scraper-week4`, itself derived from the earlier
`/opt/maps-scraper` deployment). Everything in `code/` is a verbatim copy pulled
from that server on 2026-09-02 while the run was live and healthy (0 restarts,
0 OOM-kills). Use this folder to stand the same scraper up on a fresh server.

## What's in `code/`

```
googlescrap72.py                  scraping engine (selenium + chrome)
run_parallel.py                   parallel runner / scheduler / resume logic
status.sh                         progress-check script (run on the server)
snapshot.sh                       hourly zip snapshot of output/
countries/*.py                    per-country city+keyword lists (this batch: 6 countries)
requirements.txt                  exact pinned versions (pip freeze from the live venv)
maps-scraper.service.template     generic systemd unit - copy, don't run as-is
```

`AS_DEPLOYED_maps-scraper-week4.service` (one level up) is the *actual* unit file
running on the server right now, kept verbatim for reference. It points at a
shared venv (`/opt/maps-scraper/venv`, from the earlier project) rather than a
self-contained one - a shortcut taken because that venv already existed on this
particular box. The `.template` file above is the clean, self-contained version
to use on a new server; don't copy `AS_DEPLOYED_*` directly.

## Two fixes already baked into this copy of `googlescrap72.py` - do not lose them

### 1. Non-Latin keyword filenames (the important one)

`safe_filename()` strips every non-Latin character. Without the fix, Japanese /
Arabic / Hindi / Cyrillic keywords all collapse to the same filename per city
(`japan_tokyo___comprehensive.json`), and the runner's resume-check treats the
first keyword's file as proof the *whole city* is done - silently skipping every
other keyword. This cost ~95% of Japan's data on the original run before it was
caught. The fix (already in this file, around `safe_filename()`):

```python
def safe_filename(name: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9_\-]+', "_", name).lower()
    if slug.strip("_-") == "":
        slug = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    return slug
```

Before reusing this engine with ANY new country file, check whether its keywords
are non-Latin (`grep` the keyword list for non-ASCII), and if so, verify no two
keywords for the same city produce the same filename - a five-line Python check,
see the "pre-flight" pattern below.

### 2. Memory-bound, not CPU-bound

Chrome workers are the constraint, not cores. On an 11GB box, 6 parallel workers
peaked past the 9GB memory cap and got OOM-killed roughly every 13 minutes -
before a single combo (which takes 20-50 min) could ever finish, i.e. total
livelock, zero net progress despite the service "running". Dropping to 4 workers
fixed it completely (0 OOM-kills across the following multi-week run). Do not
raise `--workers` past what memory allows just because idle CPU looks available.

**Sizing rule of thumb**: budget ~1.5-2GB per Chrome worker, leave several GB of
headroom below the box's total RAM. On 11GB, 4 workers is the proven number.
On a bigger box, scale up proportionally - but re-verify with a real soak test
(see below), don't just extrapolate.

## Fresh-server setup

1. **Chrome + matching chromedriver** (the hard part - there is no `apt install
   google-chrome` step here, it's a manual matched pair):
   - Server currently runs **Chrome for Testing 151.0.7922.76** at `/opt/chrome/chrome`
     and **ChromeDriver 151.0.7922.76** at `/opt/chromedriver-linux64/chromedriver`.
   - Chrome for Testing builds + matching chromedriver: https://googlechromelabs.github.io/chrome-for-testing/
   - Symlink both onto PATH: `ln -s /opt/chrome/chrome /usr/local/bin/chrome`
     and `ln -s /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver`.
   - **Versions must match** (chromedriver major version = chrome major version)
     or every scrape fails instantly at driver startup.

2. **Python venv + deps**:
   ```
   python3 -m venv /opt/maps-scraper/venv
   /opt/maps-scraper/venv/bin/pip install -r requirements.txt
   ```

3. **Layout**: copy `googlescrap72.py`, `run_parallel.py`, `status.sh`,
   `snapshot.sh`, and a `countries/` folder with the country files for the new
   batch into `/opt/maps-scraper/`. Create `output/`, `logs/`, `state/`,
   `snapshots/` alongside them (empty dirs, the scripts populate them).

4. **Set the country list and priority order** in `run_parallel.py`
   (`DEFAULT_COUNTRIES` near the top, or pass `--countries a b c` on the command
   line / in the systemd `ExecStart`). Order matters: countries are processed
   front-to-back, so put anything time-sensitive or never-before-scraped first,
   and known-slow non-Latin countries (Japan, Arabic-keyword countries) toward
   the end unless they're the priority.

5. **Swap**, if the box doesn't already have some (cushions a memory spike into
   a slowdown instead of an instant OOM-kill - this is what turned the
   memory-cap hits from kills into no-ops on the original run):
   ```
   fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
   echo "/swapfile none swap sw 0 0" >> /etc/fstab
   sysctl -w vm.swappiness=10
   ```

6. **systemd**: copy `maps-scraper.service.template` to
   `/etc/systemd/system/maps-scraper.service`, fix any paths, adjust
   `--workers` for the box's actual RAM, `daemon-reload`, `enable`, `start`.

7. **Pre-flight before starting the real run** - always, especially with a new
   country file:
   - Import each country module, generate every `(city, keyword)` filename the
     fixed `safe_filename()` would produce, and check for collisions (should be
     zero - see the pattern used for week4's India/Japan files, which have
     non-Latin keywords).
   - Run a tiny slice (a handful of combos) manually first to confirm Chrome
     launches, the resume-check works, and output files land where expected.
   - Only then start the full service.

8. **Soak-test the memory tuning** on the new box for ~30-60 minutes after
   starting before considering it "launched" - watch `memory.current` in the
   service's cgroup (`/sys/fs/cgroup/system.slice/<service>.service/memory.current`)
   and confirm `memory.events` stays at `oom_kill 0`. If it climbs past
   `MemoryHigh` and keeps climbing rather than plateauing/dropping, workers is
   too high for that box's RAM - lower it before it hits `MemoryMax`.

## Checking progress

`status.sh` (copy it to the server, `chmod +x`, run it there) reports combos
done / total, per-country completion, and current merged output size. It is
resume-safe and can be run at any time without affecting the live scrape.

**Caveat**: `status.sh`'s per-country percentage is based on a counter, not a
disk check - it can over-report if any files predate the filename fix (an old
collapsed `..._comprehensive.json` counts as "done" even though it only holds
one keyword's data). Cross-check with `ls output/<country> | wc -l` against the
country's real `cities x keywords` count if a percentage looks off.

## What NOT to change without re-testing

- Don't raise `--workers` without a fresh soak test on that specific box's RAM.
- Don't touch `safe_filename()` without re-running the collision pre-flight.
- Don't assume `MemoryMax` alone is enough - it was, and it caused the original
  livelock. `MemoryHigh` + swap is what fixed it.
